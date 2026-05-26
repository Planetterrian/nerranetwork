# Planetterrian Daily - Full Automation Guide

## ✅ Complete Automation Setup

The Planetterrian Daily system is now **fully automated** via GitHub Actions. Every day, the workflow will:

1. ✅ **Generate Daily Digest** - Fetch science/longevity/health news from RSS feeds (X posts currently disabled)
2. ✅ **Post to X** - Automatically post the digest to @planetterrian
3. ✅ **Generate Podcast Script** - Create natural podcast script using Grok AI
4. ✅ **Create Podcast Audio** - Generate audio using ElevenLabs TTS
5. ✅ **Update RSS Feed** - Add new episode to `planetterrian_podcast.rss`
6. ✅ **Generate Cost File** - Track and save API usage/costs to JSON file
7. ✅ **Commit & Push** - Automatically commit all files to GitHub

## 📅 Schedule

The workflow runs **daily at 8:00 AM EDT (12:00 UTC / 5:00 AM PDT)**.

You can also manually trigger it:
- Go to **Actions** tab → **Planetterrian Daily** → **Run workflow**

## 🔐 Required GitHub Secrets

All secrets are already configured:
- ✅ `GROK_API_KEY` (shared with Tesla show)
- ✅ `ELEVENLABS_API_KEY` (ElevenLabs TTS)
- ✅ `PLANETTERRIAN_X_CONSUMER_KEY`
- ✅ `PLANETTERRIAN_X_CONSUMER_SECRET`
- ✅ `PLANETTERRIAN_X_ACCESS_TOKEN`
- ✅ `PLANETTERRIAN_X_ACCESS_TOKEN_SECRET`
- ✅ `PLANETTERRIAN_X_BEARER_TOKEN`

Optional (fallback only):
- `ELEVENLABS_API_KEY` (only if you switch `PLANETTERRIAN_TTS_PROVIDER=elevenlabs`)

## 📁 Generated Files

After each run, these files are automatically committed to the repository:

### In `digests/planetterrian/` directory:
- `Planetterrian_Daily_YYYYMMDD.md` - The X thread/digest
- `Planetterrian_Daily_EpXXX_YYYYMMDD.mp3` - Podcast audio file
- `podcast_transcript_YYYYMMDD.txt` - Podcast script/transcript
- `raw_data_YYYY-MM-DD.json` - Raw news articles (and X posts if enabled)
- `raw_data_YYYY-MM-DD.html` - HTML view of raw data (optional)
- `credit_usage_YYYY-MM-DD_epXXX.json` - API usage and cost tracking

### In root directory:
- `planetterrian_podcast.rss` - RSS feed (updated with each new episode)

## 🔍 Monitoring

### Check Workflow Status
1. Go to **Actions** tab in your repository
2. Click **Planetterrian Daily** workflow
3. View the latest run to see:
   - ✅ Success/failure status
   - 📊 Generated files list
   - 💰 API usage logs
   - 🐛 Any errors

### Verify Output
After each successful run:
1. Check **X account** (@planetterrian) - should see new post
2. Check **RSS feed**: `https://raw.githubusercontent.com/Planetterrian/nerranetwork/main/planetterrian_podcast.rss`
3. Check **digests/** folder - should see new files
4. Check **credit_usage_*.json** - see API costs

## 🛠️ Workflow File

The automation is configured in:
- `.github/workflows/planetterrian-daily.yml`

## ⚙️ Script Configuration

The script (`digests/planetterrian.py`) is configured for full automation:
- `TEST_MODE = False` - Full run (not test mode)
- `ENABLE_X_POSTING = True` - Posts to X automatically
- `ENABLE_PODCAST = True` - Generates podcast and updates RSS

## 🚨 Troubleshooting

### Workflow Fails
1. Check **Actions** tab for error messages
2. Verify all GitHub Secrets are set correctly
3. Check if API rate limits were hit
4. Review logs in the workflow run

### No Files Generated
- Check if script encountered errors
- Verify API keys are valid
- Check if there was news content to process

### X Post Not Appearing
- Check X API credentials in GitHub Secrets
- Verify @planetterrian account has posting permissions
- Check workflow logs for X API errors

### RSS Feed Not Updating
- Verify podcast was generated successfully
- Check if RSS feed file exists in repository
- Review RSS feed update logs in workflow

## 📊 Cost Tracking

Each run generates a `credit_usage_YYYY-MM-DD_epXXX.json` file with:
- Grok API token usage and costs
- TTS character usage and cost (ElevenLabs)
- X API call counts
- Total estimated cost

## 🎯 Next Steps

1. ✅ **Workflow is ready** - Will run automatically daily
2. ✅ **All secrets configured** - Automation is enabled
3. 📱 **Monitor first run** - Check Actions tab after first scheduled run
4. 🌐 **Set up GitHub Pages** - Configure `planetterrian.html` if needed
5. 🎨 **Add podcast cover image** - Create `planetterrian-podcast-image.jpg` for RSS feed

## 📝 Manual Run

To test the automation manually:
1. Go to **Actions** → **Planetterrian Daily**
2. Click **"Run workflow"** button
3. Click **"Run workflow"** (green button)
4. Watch it run in real-time

---

**Everything is automated!** 🎉 Just monitor the first few runs to ensure everything works correctly.

