"""Streamlit app for Travel Verdict AI."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Tuple

import streamlit as st
from dotenv import load_dotenv

from agents import ContextAgent, DecisionAgent, WeatherAgent
from memory import MemoryRecord, TravelMemoryStore
from tools import calculate_distance_km

load_dotenv()


DECISION_RANK = {"Go": 2, "Maybe": 1, "Avoid": 0}


def _clear_app_state() -> None:
    """Clear Streamlit session state and reset key input widgets."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["location_input"] = ""
    st.session_state["date_input"] = "this weekend"
    st.session_state["preference_note_input"] = ""
    st.session_state["origin_input"] = ""


def _decision_color(decision: str) -> str:
    if decision == "Go":
        return "#1b5e20"
    if decision == "Avoid":
        return "#b71c1c"
    return "#f57f17"


def _decision_emoji(decision: str) -> str:
    if decision == "Go":
        return "✅"
    if decision == "Avoid":
        return "❌"
    return "⚠️"


def _emit_react_steps(steps: List[str], sink: List[str]) -> None:
    for step in steps:
        print(step)
        sink.append(step)


def _render_weather_summary(selected_result: Dict) -> None:
    weather_raw = selected_result["weather_raw"]
    weather_summary = selected_result["weather_summary"]
    destination_label = f"{selected_result['destination']}, {selected_result['country']}"
    dates = weather_raw.get("dates", [])
    date_range = f"{dates[0]} to {dates[-1]}" if dates else "N/A"

    st.markdown(f"**Destination:** {destination_label}")
    st.markdown(f"**Forecast Window:** {date_range}")

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Avg Temperature", f"{weather_summary.get('avg_temp_c', 'N/A')} C")
    metric_col2.metric("Max Rain Probability", f"{weather_summary.get('max_rain_probability', 'N/A')}%")
    metric_col3.metric("Max Wind", f"{weather_summary.get('max_wind_kmh', 'N/A')} km/h")

    def _value_at(values: List, index: int):
        return values[index] if index < len(values) else None

    daily_rows = []
    min_temps = weather_raw.get("temperature_min", [])
    max_temps = weather_raw.get("temperature_max", [])
    rain_probs = weather_raw.get("precipitation_probability_max", [])
    winds = weather_raw.get("windspeed_max", [])
    for idx, forecast_date in enumerate(dates):
        daily_rows.append(
            {
                "Date": forecast_date,
                "Min Temp (C)": _value_at(min_temps, idx),
                "Max Temp (C)": _value_at(max_temps, idx),
                "Rain Chance (%)": _value_at(rain_probs, idx),
                "Wind (km/h)": _value_at(winds, idx),
            }
        )
    if daily_rows:
        with st.expander("View Daily Breakdown"):
            st.table(daily_rows)


def _render_comparison_summary(results: List[Dict], selected_result: Dict) -> None:
    comparison_rows = []
    for item in results:
        summary = item["weather_summary"]
        comparison_rows.append(
            {
                "Destination": f"{item['destination']}, {item['country']}",
                "Decision": item["decision"],
                "Avg Temp (C)": summary.get("avg_temp_c"),
                "Max Rain (%)": summary.get("max_rain_probability"),
                "Max Wind (km/h)": summary.get("max_wind_kmh"),
                "Transport": item.get("transport_mode", "N/A"),
            }
        )
    st.markdown("### Comparison Snapshot")
    st.table(comparison_rows)

    best_rain = selected_result["weather_summary"].get("max_rain_probability")
    best_temp = selected_result["weather_summary"].get("avg_temp_c")
    st.info(
        "Why this destination won: "
        f"{selected_result['destination']} had the strongest combined score "
        f"(decision={selected_result['decision']}, rain={best_rain}%, avg_temp={best_temp} C)."
    )


def _run_one_destination(
    destination: str,
    date_context: Dict,
    user_query: str,
    preference_note: str,
    origin_location: str,
    weather_agent: WeatherAgent,
    decision_agent: DecisionAgent,
    memory_store: TravelMemoryStore,
) -> Tuple[Dict, List[str]]:
    react_logs: List[str] = [f"--- Handoff: ContextAgent -> WeatherAgent ({destination}) ---"]
    start_date = date.fromisoformat(date_context["start_date"])
    end_date = date.fromisoformat(date_context["end_date"])

    weather_result = weather_agent.run(destination, start_date, end_date)
    _emit_react_steps(weather_result["react_steps"], react_logs)

    react_logs.append("--- Handoff: WeatherAgent -> DecisionAgent ---")
    memory_query = f"{user_query} destination:{destination} preference:{preference_note}"
    memory_hits = memory_store.retrieve_similar(memory_query, top_k=3)
    react_logs.append(f"Observation: Retrieved {len(memory_hits)} similar past memories.")
    distance_km = None
    distance_context = None
    if origin_location.strip():
        react_logs.append("Thought: Estimate route distance for better transport recommendation.")
        react_logs.append("Action: Call Distance Tool")
        distance_context = calculate_distance_km(origin_location, destination)
        distance_km = distance_context["distance_km"]
        react_logs.append(
            f"Observation: Estimated trip distance is {distance_km} km "
            f"({distance_context['origin_resolved']} -> {distance_context['destination_resolved']})."
        )

    decision_result = decision_agent.decide(
        destination=destination,
        date_context=date_context,
        weather_data=weather_result["weather"],
        retrieved_memory=memory_hits,
        preference_note=preference_note,
        distance_km=distance_km,
    )
    _emit_react_steps(decision_result["react_steps"], react_logs)

    memory_store.add_memory(
        MemoryRecord(
            query_text=memory_query,
            decision=decision_result["decision"],
            reason=decision_result["reason"],
            suggestion=decision_result["suggestion"],
            preference_note=preference_note,
        )
    )

    return {
        "destination": weather_result["destination"],
        "country": weather_result["country"],
        "weather_summary": weather_result["weather"]["summary"],
        "weather_raw": weather_result["weather"],
        "decision": decision_result["decision"],
        "reason": decision_result["reason"],
        "suggestion": decision_result["suggestion"],
        "transport_mode": decision_result.get("transport_mode", "Not available"),
        "transport_reason": decision_result.get("transport_reason", ""),
        "distance_context": distance_context,
    }, react_logs


def _pick_better_option(results: List[Dict]) -> Dict:
    return sorted(
        results,
        key=lambda item: (
            DECISION_RANK.get(item["decision"], 1),
            -(item["weather_summary"].get("max_rain_probability") or 100),
            -(item["weather_summary"].get("avg_temp_c") or 0),
        ),
        reverse=True,
    )[0]


def main() -> None:
    st.set_page_config(page_title="Travel Verdict AI", page_icon="🌍", layout="centered")
    st.title("Travel Verdict AI")
    st.caption("Multi-agent AI system with tools, ReAct reasoning, and memory")

    with st.sidebar:
        st.subheader("Settings")
        origin_location = st.text_input(
            "Starting City (optional)",
            placeholder="Example: Kochi",
            help="Used to estimate route distance for better transport recommendations.",
            key="origin_input",
        )
        preference_note = st.text_input(
            "Preference (optional)",
            placeholder="Example: I prefer cool weather",
            key="preference_note_input",
        )
        st.markdown("Set `GROQ_API_KEY` in your environment for LLM-based decisions.")

    location_input = st.text_input(
        "Destination (City or Comparison)",
        placeholder="Enter a city",
        help=(
            "Enter city names or a sentence with destinations. "
            "Examples: 'Idukki', 'Munnar vs Ooty', 'I am deciding between Chennai and Munnar'."
        ),
        key="location_input",
    )
    date_input = st.text_input(
        "Travel Date / Timeframe",
        value="this weekend",
        placeholder="e.g., tomorrow, this weekend, 2026-05-10",
        help="Enter a specific date (YYYY-MM-DD) or a phrase like 'this weekend', 'tomorrow', or 'next Friday'.",
        key="date_input",
    )

    action_col, clear_col = st.columns([3, 1])
    analyze_clicked = action_col.button("Analyze", type="primary")
    clear_col.button("Clear", on_click=_clear_app_state)

    if analyze_clicked:
        if not location_input.strip() or not date_input.strip():
            st.error("Please provide both location and date input.")
            st.stop()

        context_agent = ContextAgent()
        weather_agent = WeatherAgent()
        decision_agent = DecisionAgent()
        memory_store = TravelMemoryStore()

        try:
            with st.spinner("Analyzing weather, context, memory, and travel suitability..."):
                user_query = f"Should I travel to {location_input} on {date_input}?"
                context = context_agent.prepare_context(location_input, date_input, user_query=user_query)
                all_react_steps = ["--- ContextAgent ---"]
                _emit_react_steps(context.react_steps, all_react_steps)

                destination_results: List[Dict] = []
                for destination in context.destinations:
                    result, logs = _run_one_destination(
                        destination=destination,
                        date_context=context.date_context,
                        user_query=context.user_query,
                        preference_note=preference_note,
                        origin_location=origin_location,
                        weather_agent=weather_agent,
                        decision_agent=decision_agent,
                        memory_store=memory_store,
                    )
                    destination_results.append(result)
                    all_react_steps.extend(logs)

                selected_result = destination_results[0]
                compare_text = ""
                if context.intent == "compare_destinations" and len(destination_results) > 1:
                    selected_result = _pick_better_option(destination_results)
                    compare_text = (
                        "Compared destinations and selected best option: "
                        f"{selected_result['destination']} ({selected_result['decision']})."
                    )

            st.success("Analysis complete.")
            st.subheader("🌦 Weather Summary")
            _render_weather_summary(selected_result)
            if compare_text:
                st.info(compare_text)
                _render_comparison_summary(destination_results, selected_result)

            decision_color = _decision_color(selected_result["decision"])
            st.subheader("🤖 Decision")
            st.markdown(
                f"""
<div style="padding:12px;border-radius:10px;background:{decision_color};color:white;font-size:20px;font-weight:700;">
Decision: {selected_result['decision']}
</div>
                """,
                unsafe_allow_html=True,
            )

            st.subheader("🧠 Reasoning")
            for step in all_react_steps:
                st.code(step, language="text")

            st.subheader("💡 Suggestion")
            st.write(selected_result["suggestion"])
            st.write(f"Reason: {selected_result['reason']}")

            st.subheader("🚗 Transport Recommendation")
            st.write(f"Preferred Transport: {selected_result['transport_mode']}")
            if selected_result["transport_reason"]:
                st.write(f"Why: {selected_result['transport_reason']}")
            if selected_result.get("distance_context"):
                st.write(f"Estimated Distance: {selected_result['distance_context']['distance_km']} km")

            st.markdown("### Output Format")
            st.write(f"Decision: {_decision_emoji(selected_result['decision'])} {selected_result['decision']}")
            st.write(f"Reason: {selected_result['reason']}")
            st.write(f"Suggestion: {selected_result['suggestion']}")
            st.write(f"Transport: {selected_result['transport_mode']}")
            if selected_result.get("distance_context"):
                st.write(f"Distance: {selected_result['distance_context']['distance_km']} km")

        except Exception as error:
            st.error(f"Unable to process request: {error}")


if __name__ == "__main__":
    main()
