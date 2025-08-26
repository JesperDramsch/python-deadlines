# Development Guide for Python Deadlines

## Quick Development Builds

The full site build with all languages and historical data can take a long time. We provide several development configurations for faster iteration:

### Available Commands

```bash
# Full production build (all languages, all data) - SLOW
pixi run serve

# Development build (English + German, no archive/legacy) - FAST
pixi run serve-dev

# Minimal build (English only, minimal plugins) - FASTEST
pixi run serve-minimal

# Fast incremental build (skips initial build)
pixi run serve-fast
```

### Build Time Comparison

| Command | Languages | Archive/Legacy | Plugins | Build Time |
|---------|-----------|----------------|---------|------------|
| `serve` | All 9 | Yes | All | ~3-5 minutes |
| `serve-dev` | EN, DE | No | Most | ~30-45 seconds |
| `serve-minimal` | EN only | No | Minimal | ~15-20 seconds |
| `serve-fast` | EN, DE | No | Most | ~10 seconds (incremental) |

### Configuration Files

- **`_config.yml`** - Main production configuration
- **`_config.dev.yml`** - Development config (EN+DE, no historical data)
- **`_config.minimal.yml`** - Minimal config (EN only, bare essentials)

### How It Works

Jekyll allows layering configurations using the `--config` flag:
```bash
jekyll serve --config _config.yml,_config.dev.yml
```

Later configs override earlier ones, so `_config.dev.yml` overrides specific settings from `_config.yml`.

### What Gets Excluded in Dev Mode

**Development Mode (`serve-dev`):**
- Languages: Only English and German
- Archive data: Not processed
- Legacy data: Not processed
- Some plugins: Sitemap disabled
- Analytics: Disabled

**Minimal Mode (`serve-minimal`):**
- Languages: Only English
- Only current conferences processed
- Minimal plugins (no SEO, maps, sitemap)
- All other languages excluded from file watching
- Maximum speed optimizations

### When to Use Each Mode

- **`serve`** - Final testing before deployment, checking all languages
- **`serve-dev`** - General development, testing features
- **`serve-minimal`** - Quick iterations, CSS/JS development
- **`serve-fast`** - Continuous development with auto-reload

### Tips for Faster Development

1. **Use minimal mode for CSS/JS work:**
   ```bash
   pixi run serve-minimal
   ```

2. **Skip link checking when sorting:**
   ```bash
   pixi run sort  # Uses --skip_links by default
   ```

3. **Use incremental builds:**
   ```bash
   pixi run serve-fast
   ```

4. **Exclude files from watch:**
   Add large files or directories to `exclude:` in dev configs

5. **Clear Jekyll cache if builds are slow:**
   ```bash
   rm -rf _site .jekyll-cache
   ```

### Custom Development Configuration

You can create your own config for specific needs:

```yaml
# _config.custom.yml
languages: [ "en", "es" ]  # Your preferred languages
page_gen:
  # Your custom page generation rules
```

Then use it:
```bash
bundler exec jekyll serve --config _config.yml,_config.custom.yml
```

### Troubleshooting

**Build still slow?**
- Clear cache: `rm -rf _site .jekyll-cache`
- Check for large files in `_data/`
- Use `--profile` flag to identify bottlenecks

**Missing content in dev mode?**
- Check which config you're using
- Archive/legacy conferences won't appear in dev mode
- Some languages are excluded

**Changes not appearing?**
- Restart Jekyll if you modify `_config*.yml`
- Check if files are excluded in the config
- Try without `--incremental` flag
