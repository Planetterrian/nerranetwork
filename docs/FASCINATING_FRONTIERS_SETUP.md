# Fascinating Frontiers Setup Guide

## Overview

Fascinating Frontiers is a daily space and astronomy news digest and podcast, following the same structure as Planetterrian Daily but focused on space exploration, astronomy discoveries, and cosmic phenomena.

## Files Created

1. **`digests/fascinating_frontiers.py`** - Main script for generating daily digest and podcast
2. **`fascinating_frontiers_podcast.rss`** - RSS feed for the podcast (will be generated automatically)
3. **`.github/workflows/fascinating-frontiers-daily.yml`** - GitHub Actions workflow for automated daily runs

## Environment Variables Required

### For Local Runs

Add these to your `.env` file (uses the same APIs as planetterrian.py):

```bash
# Grok API (same as Tesla show and Planetterrian)
GROK_API_KEY=your_grok_api_key

# TTS (ElevenLabs)
ELEVENLABS_API_KEY=your_elevenlabs_api_key
# ELEVENLABS_VOICE_ID=your_elevenlabs_voice_id  # optional, uses default if not set

# X API credentials for @planetterrian account (same as Planetterrian - posts to same account)
PLANETTERRIAN_X_CONSUMER_KEY=your_consumer_key
PLANETTERRIAN_X_CONSUMER_SECRET=your_consumer_secret
PLANETTERRIAN_X_ACCESS_TOKEN=your_access_token
PLANETTERRIAN_X_ACCESS_TOKEN_SECRET=your_access_token_secret
PLANETTERRIAN_X_BEARER_TOKEN=your_bearer_token
```

### For GitHub Actions (Automated Daily Runs)

If you want to run Fascinating Frontiers automatically via GitHub Actions, add these as **GitHub Secrets**:

1. Go to your repository → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"** and add:

**Required Secrets:**
- `GROK_API_KEY` - Your Grok/X.AI API key (shared with Tesla show and Planetterrian)

Optional (fallback only):
- `ELEVENLABS_API_KEY` - Only needed if you switch `FASCINATING_FRONTIERS_TTS_PROVIDER=elevenlabs`

**Required for X Posting:**
- `PLANETTERRIAN_X_CONSUMER_KEY` - X API consumer key for @planetterrian (same as Planetterrian)
- `PLANETTERRIAN_X_CONSUMER_SECRET` - X API consumer secret for @planetterrian (same as Planetterrian)
- `PLANETTERRIAN_X_ACCESS_TOKEN` - X API access token for @planetterrian (same as Planetterrian)
- `PLANETTERRIAN_X_ACCESS_TOKEN_SECRET` - X API access token secret for @planetterrian (same as Planetterrian)
- `PLANETTERRIAN_X_BEARER_TOKEN` - X API bearer token for @planetterrian (optional but recommended, same as Planetterrian)

**Note:** The GitHub Actions workflow (`.github/workflows/fascinating-frontiers-daily.yml`) will automatically use these secrets to create a `.env` file when running.

## Running the Script

```bash
pip install -r requirements_fascinating_frontiers.txt
cd digests
python3 fascinating_frontiers.py
```

## Features

### Content Focus
- **Space News**: Latest space missions, launches, and space agency updates
- **Astronomy Discoveries**: Cosmic phenomena, exoplanets, galaxies, black holes
- **Space Technology**: Rockets, satellites, telescopes, space stations
- **Cosmic Phenomena**: Supernovae, nebulae, star formation, cosmic events

### RSS Feeds Monitored
- NASA (multiple feeds: breaking news, image of the day, center-specific)
- Space.com
- Spaceflight Now
- SpaceNews
- Astronomy Magazine
- Sky & Telescope
- Universe Today
- European Space Agency (ESA)
- Roscosmos
- JAXA
- SpaceX
- Blue Origin
- Science journals (space-focused content)

### Brand Personality
- **Mission**: Bring the wonders of space exploration and astronomy discoveries to everyone
- **Values**: Curiosity, exploration, scientific accuracy, inspiration
- **Tone**: Inspirational, awe-inspiring, accessible, exciting, forward-thinking
- **Focus**: Latest space missions, astronomy discoveries, cosmic phenomena, and space technology breakthroughs

## Output Files

All files are saved in `digests/fascinating_frontiers/`:
- `Fascinating_Frontiers_YYYYMMDD.md` - X thread/digest
- `Fascinating_Frontiers_EpXXX_YYYYMMDD.mp3` - Podcast audio
- `podcast_transcript_YYYYMMDD.txt` - Podcast transcript
- `credit_usage_YYYY-MM-DD_epXXX.json` - API usage tracking
- `raw_data_YYYY-MM-DD.json` - Raw news data

## RSS Feed

The RSS feed is automatically generated at:
- File: `fascinating_frontiers_podcast.rss` (in project root)
- URL: `https://raw.githubusercontent.com/Planetterrian/nerranetwork/main/fascinating_frontiers_podcast.rss`

## Differences from Planetterrian Daily

1. **Content Focus**: Space/astronomy instead of science/longevity/health
2. **RSS Feeds**: Space agencies and astronomy publications instead of science journals
3. **Keywords**: Space/astronomy terms instead of science/health terms
4. **Brand Voice**: Space exploration and cosmic wonder focused
5. **File Naming**: `Fascinating_Frontiers_*` instead of `Planetterrian_Daily_*`
6. **RSS Feed**: `fascinating_frontiers_podcast.rss` instead of `planetterrian_podcast.rss`
7. **X Account**: Uses @planetterrian (same account as Planetterrian)

## Next Steps

### Local Setup
1. ✅ Add X API credentials for @planetterrian to `.env` (same as Planetterrian)
2. Test run the script: `python3 digests/fascinating_frontiers.py`

### GitHub Actions Setup (Optional - for automated daily runs)
1. Add Planetterrian X API credentials to **GitHub Secrets** (same as Planetterrian - see above)
2. The workflow file (`.github/workflows/fascinating-frontiers-daily.yml`) is already created
3. Enable workflow permissions:
   - Go to **Settings** → **Actions** → **General**
   - Under **"Workflow permissions"**, select **"Read and write permissions"**
   - Click **Save**
4. Test the workflow:
   - Go to **Actions** tab → **Fascinating Frontiers Daily** workflow
   - Click **"Run workflow"** → **"Run workflow"** (manual trigger)

### Website Setup (Optional)
1. Create a GitHub Pages site for Fascinating Frontiers (if desired)
2. Use the included page: `fascinating_frontiers.html`
2. Create podcast cover image: `fascinating-frontiers-podcast-image.jpg` (or reuse planetterrian image)
3. Submit podcast to Apple Podcasts (when ready)

## Notes

- The script uses the same Patrick voice as Tesla Shorts Time and Planetterrian
- Credit usage is tracked separately for Fascinating Frontiers
- The RSS feed is separate from both the Tesla show's feed and Planetterrian's feed
- All files are organized in `digests/fascinating_frontiers/` subdirectory
- Posts to the same X account as Planetterrian (@planetterrian)
- Uses the same APIs as planetterrian.py (GROK_API_KEY, ELEVENLABS_API_KEY, and PLANETTERRIAN_X_* credentials)

