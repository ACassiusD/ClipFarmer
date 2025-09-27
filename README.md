# How to use

### Activate Environment
`source /Users/alex.donnelly/Projects/ClipFarmer/.venv/bin/activate`

### Youtube Shorts farmer
`python /Users/alex.donnelly/Projects/ClipFarmer/shorts_codegen.py`
- outputs to youtube.json
- Can change starting URL in `youtube_shorts_farmer.py` 
  - `START_URL = "https://www.youtube.com/shorts/hhoIPjrZeVs"
`

### Instagram Reel farmer
`source /Users/alex.donnelly/Projects/ClipFarmer/.venv/bin/activate`
`python /Users/alex.donnelly/Projects/ClipFarmer/instagram_reels_farmer.py`


### Create a new Recording 
```
python -m playwright codegen --target python-async \
  --output /Users/alex.donnelly/Projects/ClipFarmer/OUTPUT_NAME_HERE.py \
  https://www.youtube.com/@YouTube/shorts
```