# Vercel Function Settings

Since `builds` and `functions` cannot be used together in `vercel.json`, configure these settings in the Vercel dashboard:

## Required Settings for `api/index.py`:

1. **Max Duration**: 300 seconds (5 minutes)
   - Go to: Project Settings → Functions → `api/index.py`
   - Set "Max Duration" to 300

2. **Memory**: 1024 MB
   - Set "Memory" to 1024 MB

## Alternative: Environment Variables

You can also set these via Vercel CLI:
```bash
vercel env add VERCEL_FUNCTION_MAX_DURATION
vercel env add VERCEL_FUNCTION_MEMORY
```

Or configure in the Vercel dashboard under Project Settings → Environment Variables.

