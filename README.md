# Travel Verdict AI

Travel Verdict AI is a multi-agent Streamlit app that helps users decide whether to travel to a destination based on weather, intent, memory, and route context.

## Highlights

- **Multi-agent workflow**
  - `ContextAgent`: extracts destinations from natural language and parses date intent
  - `WeatherAgent`: resolves location coordinates and fetches weather forecast
  - `DecisionAgent`: combines weather + memory + preferences (+ optional distance) to return:
    - Decision (`Go` / `Avoid` / `Maybe`)
    - Reason
    - Suggestion
    - Transport recommendation
- **ReAct trace visibility**
  - Explicit `Thought -> Action -> Observation -> Final Answer` logs shown in UI
- **Vector memory (FAISS)**
  - Stores past queries and decisions
  - Retrieves similar memories for current decisions
- **Comparison mode**
  - Supports natural sentence inputs for comparing multiple places
  - Shows comparison snapshot table and winner rationale
- **Distance-aware transport advice**
  - Optional starting city
  - Distance is estimated and used in transport recommendation

## Project Structure

```text
smart travel decision agent/
├── agents/
│   ├── context_agent.py
│   ├── weather_agent.py
│   └── decision_agent.py
├── tools/
│   ├── date_parser_tool.py
│   ├── location_parser_tool.py
│   ├── geocoding_tool.py
│   ├── weather_tool.py
│   └── distance_tool.py
├── memory/
│   └── vector_memory.py
├── app.py
├── requirements.txt
└── .env.example
```

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure environment variables:

Create a `.env` file in project root:

```env
GROQ_API_KEY=your_groq_api_key_here
```

(An example is available in `.env.example`.)

## Run

```bash
streamlit run app.py
```

## Input Examples

- Single destination:
  - `Idukki`
  - `Should I go to Goa this weekend?`
- Comparison:
  - `Munnar vs Ooty`
  - `I am deciding between Chennai and Munnar this weekend`
- Date / timeframe:
  - `tomorrow`
  - `this weekend`
  - `2026-05-10`

## UI Output Sections

- 🌦 Weather Summary (metrics + daily breakdown)
- 🤖 Decision (highlighted by decision color)
- 🧠 Reasoning (full ReAct trace)
- 💡 Suggestion
- 🚗 Transport Recommendation
- Comparison Snapshot (only for multi-destination queries)

## Notes

- Geocoding now uses candidate ranking and ambiguity detection (instead of hardcoded city aliases).
- If a location is ambiguous, the app asks the user to clarify with country/state.
- If `GROQ_API_KEY` is missing, the decision and transport fallback logic still works deterministically.
