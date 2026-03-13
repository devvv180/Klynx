# LLM-Based Event Filtering for Client Risk Dashboard

## Problem Solved

The Client Risk Dashboard was showing ALL 188 events as "relevant" to Meridian Lifesciences (pharma company), including:
- North Korea nuclear threats
- Fashion week collaborations
- Earthquakes in Turkey
- Tech product launches

These events matched on loose criteria (geography, keywords) but had NO actual business relevance to a pharmaceutical manufacturer.

## Solution

Implemented LLM-based filtering that:
1. **Understands business context** - Knows Meridian is a pharma company with FDA exposure, China sourcing, India manufacturing
2. **Evaluates semantic relevance** - Distinguishes between "FDA approves cancer drug" (relevant) vs "US announces steel tariffs" (not relevant)
3. **Runs automatically** - Filters events in background on first dashboard load
4. **Persists results** - Saves filtered events to `data/llm_filtered_relevant_events.jsonl` for fast subsequent loads

## How It Works

### Automatic Mode (Recommended)

The dashboard automatically runs LLM filtering when:
- First time loading (no filtered events file exists)
- Client profile changes (client_data.json modified)
- Event dataset changes (new events added)

Just open the dashboard and it will handle everything!

### Manual Pre-filtering (Optional)

If you want to pre-generate filtered events before opening the dashboard:

**Windows:**
```cmd
cd Klynx\risk_engine
set GROQ_API_KEY=your-key-here
run_llm_filter.bat
```

**Linux/Mac:**
```bash
cd Klynx/risk_engine
export GROQ_API_KEY='your-key-here'
chmod +x run_llm_filter.sh
./run_llm_filter.sh
```

**Python directly:**
```bash
cd Klynx/risk_engine
python llm_relevance_filter.py
```

## Setup Requirements

### 1. Set Groq API Key

Get a free API key from https://console.groq.com/

**Windows PowerShell:**
```powershell
$env:GROQ_API_KEY='your-key-here'
```

**Windows CMD:**
```cmd
set GROQ_API_KEY=your-key-here
```

**Linux/Mac:**
```bash
export GROQ_API_KEY='your-key-here'
```

**Permanent (add to environment variables):**
- Windows: System Properties → Environment Variables → New
- Linux/Mac: Add to `~/.bashrc` or `~/.zshrc`

### 2. Alternative: Use Ollama (Local LLM)

If you don't want to use Groq, you can run Ollama locally:

```bash
# Install Ollama from https://ollama.ai
ollama pull llama3.1:70b

# Set environment variable
export LLM_PROVIDER=ollama
export OLLAMA_URL=http://127.0.0.1:11434
```

## Expected Results

For Meridian Lifesciences (pharma), filtering should reduce events from **188 → ~30-50** truly relevant events:

### ✅ Relevant Events Include:
- FDA drug approvals/rejections
- Pharma M&A and partnerships
- Regulatory changes (FDA, EU, India)
- Supply chain disruptions in China/India
- API/raw material shortages
- Manufacturing facility issues
- Clinical trial results
- Generic drug competition
- Healthcare policy changes

### ❌ Filtered Out:
- Geopolitical conflicts (unless affecting pharma supply chains)
- General tech announcements
- Natural disasters (unless affecting manufacturing regions)
- Fashion/consumer goods
- Financial market news (unless pharma-specific)

## Testing

Test the filtering on first 10 events:

```bash
cd Klynx/risk_engine
python test_llm_filter.py
```

This will show you:
- Which events are marked relevant/not relevant
- LLM's reasoning for each decision
- Overall filtering rate

## Files Created/Modified

### New Files:
1. **`llm_relevance_filter.py`** - Core LLM filtering logic
2. **`test_llm_filter.py`** - Test script for validation
3. **`run_llm_filter.bat`** - Windows batch script
4. **`run_llm_filter.sh`** - Linux/Mac shell script
5. **`data/llm_filtered_relevant_events.jsonl`** - Output (generated)

### Modified Files:
1. **`pages/2_Client_Risk_Analysis.py`** - Auto-detect and use filtered events

## Technical Details

**LLM Model:** Groq Llama 3.3 70B Versatile
- Fast inference (~1-2 seconds per event)
- Strong reasoning capabilities
- Excellent at understanding business context

**Cost:** ~$0.01-0.02 for 188 events (very cheap with Groq)

**Processing Time:** 2-3 minutes for full dataset

**Caching:** Results are cached in `llm_filtered_relevant_events.jsonl`
- Only re-runs if source data changes
- Fast subsequent dashboard loads

## Troubleshooting

### "GROQ_API_KEY not set"
Set the environment variable as shown in Setup section above.

### "ModuleNotFoundError: No module named 'groq'"
The code now uses urllib (built-in), no external dependencies needed!

### "LLM filtering timed out"
- Increase timeout in dashboard code (currently 5 minutes)
- Or run manually with `python llm_relevance_filter.py`

### "All events still showing"
- Check if `llm_filtered_relevant_events.jsonl` exists in `data/` folder
- Delete it and let dashboard regenerate
- Check for errors in Streamlit console

### "Too few/many events filtered"
- Adjust the prompt in `llm_relevance_filter.py` line ~70
- Make stricter: Add "ONLY mark relevant if DIRECTLY impacts pharma operations"
- Make looser: Remove "Be STRICT" instruction

## Performance Tips

1. **Pre-filter once** - Run `run_llm_filter.bat` before demo/presentation
2. **Cache results** - Don't delete `llm_filtered_relevant_events.jsonl` unless data changes
3. **Use Groq** - Much faster than Ollama for this use case
4. **Batch processing** - Current implementation processes one event at a time (could be optimized)

## Future Enhancements

1. **Confidence threshold** - Filter by LLM confidence score (e.g., only show >0.8)
2. **Multi-model consensus** - Use 2-3 LLMs and take majority vote
3. **Active learning** - Let users mark events as relevant/not relevant to improve filtering
4. **Batch API calls** - Process multiple events per API call (faster)
5. **Incremental filtering** - Only filter new events, not entire dataset each time

## Support

If you encounter issues:
1. Check Streamlit console for error messages
2. Run `python test_llm_filter.py` to validate LLM setup
3. Check `llm_filtered_relevant_events.jsonl` was created
4. Verify GROQ_API_KEY is set correctly
