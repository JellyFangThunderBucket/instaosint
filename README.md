# Instagram OSINT Tool

InstagramOSINT collects public metadata that Instagram exposes in a profile page's HTML and saves it to a local scan directory. The project can be used from the command line or imported as a small Python module.

> This tool is for lawful OSINT and research against accounts you are authorized to review. Instagram changes its public page structure frequently, so scraping may fail when profile data is not rendered in the returned HTML.

## Collected data

The scraper attempts to collect:

1. Username
2. Profile name
3. Profile URL
4. Followers
5. Following
6. Number of posts
7. Bio
8. Profile picture URL
9. Business account flag
10. Connected Facebook page flag/data
11. External URL
12. Joined recently flag
13. Business category name
14. Private account flag
15. Verified account flag
16. Visible public post metadata
17. Optional profile picture and public post thumbnail downloads

## Install

Python 3.10+ is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Command-line usage

```bash
python3 main.py --username USERNAME
```

Useful options:

```bash
python3 main.py --username USERNAME --downloadPhotos
python3 main.py --username @USERNAME --output-dir scans
python3 main.py --username USERNAME --no-profile-picture
```

Each run creates a unique folder named after the username, such as `USERNAME/` or `USERNAME1/`, without changing the process working directory. Profile metadata is saved as pretty-printed JSON in `data.txt`; visible post metadata is saved in `posts.txt`.

## Python module usage

`InstagramOSINT.py` is intended for import into custom applications.

```python
from InstagramOSINT import InstagramOSINT

instagram = InstagramOSINT(username="USERNAMEHERE")
print(instagram.profile_data)
print(instagram["Username"])
instagram.print_profile_data()
instagram.save_data()
instagram.scrape_posts(download_images=False)
```

## Recent maintenance improvements

- Uses HTTPS and modern request headers.
- Adds request timeouts and explicit `InstagramOSINTError` exceptions instead of broad `except` blocks and interpreter exits.
- Avoids global `os.chdir()` side effects by writing through `pathlib.Path`.
- Creates unique output directories safely and writes indented UTF-8 JSON.
- Handles missing captions, missing thumbnails, and changed metadata more defensively.
- Updates dependency names and versions in `requirements.txt`.

## Disclaimer

The authors and maintainers are not responsible for misuse. Do not break the law, violate platform terms, or collect data without a lawful basis.
