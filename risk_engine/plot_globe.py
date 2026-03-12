import pandas as pd
import plotly.express as px

# Load your file
df = pd.read_json("risk_engine/data/event_severity_with_geo.json")

# Create globe visualization
fig = px.scatter_geo(
    df,
    lat="lat",
    lon="lon",
    hover_name="headline",
    size="severity_score",
    color="severity_score",
    color_continuous_scale=["green", "yellow", "red"],
    projection="orthographic"
)

fig.update_layout(
    title="Global Geopolitical Risk Events",
    height=700
)

fig.show()