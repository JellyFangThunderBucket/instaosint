#! /usr/bin/env python3
"""Instagram profile OSINT helpers.

The scraper intentionally limits itself to public profile metadata that Instagram
renders in the profile page HTML. Instagram changes that markup frequently, so
this module keeps parsing defensive and exposes clear exceptions instead of
exiting the interpreter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import random
import re
import secrets
import time
from typing import Any, Dict, Iterable, Mapping, Optional

from bs4 import BeautifulSoup
import requests


INSTAGRAM_BASE_URL = "https://www.instagram.com"
REQUEST_TIMEOUT = 15
DEFAULT_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36",
)


class colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class InstagramOSINTError(RuntimeError):
    """Raised when Instagram data cannot be fetched or parsed."""


@dataclass
class InstagramOSINT:
    """Collect public metadata for an Instagram profile.

    Parameters are intentionally optional beyond ``username`` so existing import
    usage still works: ``InstagramOSINT(username='example')`` immediately fetches
    profile data and stores it on ``profile_data``.
    """

    username: str
    output_dir: Path | str = Path(".")
    session: requests.Session = field(default_factory=requests.Session)
    request_timeout: int = REQUEST_TIMEOUT
    download_delay: tuple[float, float] = (0.25, 1.0)

    def __post_init__(self) -> None:
        self.username = self._clean_username(self.username)
        self.output_dir = Path(self.output_dir)
        self.useragents = list(DEFAULT_USER_AGENTS)
        self.profile_meta: Dict[str, Any] = {}
        self.description: Dict[str, Any] = {}
        self.profile_data: Dict[str, str] = self.scrape_profile()

    def __repr__(self) -> str:
        return f"Current Username: {self.username}"

    def __str__(self) -> str:
        return f"Current Username: {self.username}"

    def __getitem__(self, key: str) -> str:
        return self.profile_data[key]

    @staticmethod
    def _clean_username(username: str) -> str:
        cleaned = username.strip().lstrip("@")
        if not cleaned:
            raise ValueError("username cannot be empty")
        return cleaned

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(self.useragents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get(self, url: str) -> requests.Response:
        try:
            response = self.session.get(url, headers=self._headers(), timeout=self.request_timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            raise InstagramOSINTError(f"Unable to fetch {url}: {exc}") from exc

    def scrape_profile(self) -> Dict[str, str]:
        """Fetch and parse public profile data."""
        response = self._get(f"{INSTAGRAM_BASE_URL}/{self.username}/")
        soup = BeautifulSoup(response.text, "html.parser")
        self.description = self._parse_ld_json(soup)
        self.profile_meta = self._parse_profile_meta(soup)
        user = self._profile_user(self.profile_meta)

        counts = self._parse_description_counts(soup)
        return {
            "Username": str(user.get("username") or self.username),
            "Profile name": str(self.description.get("name") or user.get("full_name") or ""),
            "URL": str(self.description.get("mainEntityofPage", {}).get("@id") or f"{INSTAGRAM_BASE_URL}/{self.username}/"),
            "Followers": str(counts.get("Followers") or user.get("edge_followed_by", {}).get("count", "")),
            "Following": str(counts.get("Following") or user.get("edge_follow", {}).get("count", "")),
            "Posts": str(counts.get("Posts") or user.get("edge_owner_to_timeline_media", {}).get("count", "")),
            "Bio": str(user.get("biography") or ""),
            "profile_pic_url": str(user.get("profile_pic_url_hd") or user.get("profile_pic_url") or ""),
            "is_business_account": str(user.get("is_business_account")),
            "connected_to_fb": str(user.get("connected_fb_page")),
            "externalurl": str(user.get("external_url")),
            "joined_recently": str(user.get("is_joined_recently")),
            "business_category_name": str(user.get("business_category_name")),
            "is_private": str(user.get("is_private")),
            "is_verified": str(user.get("is_verified")),
        }

    def _parse_ld_json(self, soup: BeautifulSoup) -> Dict[str, Any]:
        tag = soup.find("script", attrs={"type": "application/ld+json"})
        if not tag or not tag.string:
            return {}
        try:
            data = json.loads(tag.string)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _parse_profile_meta(self, soup: BeautifulSoup) -> Dict[str, Any]:
        for script in soup.find_all("script"):
            text = script.string or script.get_text() or ""
            if "entry_data" not in text and "ProfilePage" not in text:
                continue
            for payload in self._json_candidates(text):
                user = self._try_extract_user(payload)
                if user:
                    return payload
        raise InstagramOSINTError(f"Username {self.username} not found or profile data is unavailable")

    @staticmethod
    def _json_candidates(text: str) -> Iterable[Mapping[str, Any]]:
        prefixes = ("window._sharedData =", "window.__additionalDataLoaded(")
        stripped = text.strip().rstrip(";")
        candidates = [stripped]
        for prefix in prefixes:
            if prefix in stripped:
                candidate = stripped.split(prefix, 1)[1].strip()
                if candidate.endswith(")"):
                    candidate = candidate[:-1]
                if candidate.startswith("'") or candidate.startswith('"'):
                    first_comma = candidate.find(",")
                    candidate = candidate[first_comma + 1 :].strip() if first_comma > -1 else candidate
                candidates.append(candidate.rstrip(";"))
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                yield parsed

    def _profile_user(self, profile_meta: Mapping[str, Any]) -> Mapping[str, Any]:
        user = self._try_extract_user(profile_meta)
        if not user:
            raise InstagramOSINTError(f"Could not parse profile data for {self.username}")
        return user

    @staticmethod
    def _try_extract_user(profile_meta: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
        try:
            user = profile_meta["entry_data"]["ProfilePage"][0]["graphql"]["user"]
            return user if isinstance(user, Mapping) else None
        except (KeyError, IndexError, TypeError):
            pass
        try:
            user = profile_meta["graphql"]["user"]
            return user if isinstance(user, Mapping) else None
        except (KeyError, TypeError):
            return None

    @staticmethod
    def _parse_description_counts(soup: BeautifulSoup) -> Dict[str, str]:
        tag = soup.find("meta", attrs={"property": "og:description"})
        if not tag:
            return {}
        content = tag.get("content", "")
        match = re.search(r"([\d.,KMB]+) Followers, ([\d.,KMB]+) Following, ([\d.,KMB]+) Posts", content)
        if not match:
            return {}
        return {"Followers": match.group(1), "Following": match.group(2), "Posts": match.group(3)}

    def scrape_posts(self, download_images: bool = True) -> Dict[int, Dict[str, str]]:
        """Scrape visible timeline post metadata and optionally thumbnails."""
        if self.profile_data.get("is_private", "").lower() == "true":
            print("[*] Private profile, cannot scrape photos!")
            return {}

        posts: Dict[int, Dict[str, str]] = {}
        edges = self._profile_user(self.profile_meta).get("edge_owner_to_timeline_media", {}).get("edges", [])
        for index, post in enumerate(edges):
            node = post.get("node", {})
            post_dir = self.output_path / str(index)
            post_dir.mkdir(parents=True, exist_ok=True)
            caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
            caption = caption_edges[0].get("node", {}).get("text", "") if caption_edges else "No Caption on this post"
            posts[index] = {
                "Caption": str(caption),
                "Number of Comments": str(node.get("edge_media_to_comment", {}).get("count", "")),
                "Comments Disabled": str(node.get("comments_disabled", "")),
                "Taken At Timestamp": str(node.get("taken_at_timestamp", "")),
                "Number of Likes": str(node.get("edge_liked_by", {}).get("count", "")),
                "Location": str(node.get("location", "")),
                "Accessibility Caption": str(node.get("accessibility_caption", "")),
            }
            if download_images:
                resources = node.get("thumbnail_resources") or []
                src = resources[-1].get("src") if resources else node.get("thumbnail_src")
                if src:
                    self._download_file(src, post_dir / f"{secrets.token_hex(6)}.jpg")
                    print("Got an Image")

        (self.output_path / "posts.txt").write_text(json.dumps(posts, indent=2), encoding="utf-8")
        return posts

    @property
    def output_path(self) -> Path:
        return Path(getattr(self, "_output_path", self.output_dir / self.username))

    def make_directory(self) -> Path:
        """Create a unique output directory without changing process cwd."""
        base = self.output_dir / self.username
        path = base
        suffix = 0
        while path.exists():
            suffix += 1
            path = self.output_dir / f"{self.username}{suffix}"
        path.mkdir(parents=True, exist_ok=False)
        self._output_path = path
        return path

    def save_data(self, download_profile_picture: bool = True) -> Path:
        """Save profile data as pretty JSON and optionally download the avatar."""
        if not hasattr(self, "_output_path"):
            self.make_directory()
        (self.output_path / "data.txt").write_text(json.dumps(self.profile_data, indent=2), encoding="utf-8")
        if download_profile_picture and self.profile_data.get("profile_pic_url"):
            self.download_profile_picture()
        print(f"Saved data to directory {self.output_path.resolve()}")
        return self.output_path

    def print_profile_data(self) -> None:
        print(colors.HEADER + "---------------------------------------------" + colors.ENDC)
        print(colors.OKGREEN + f"Results: scan for {self.profile_data['Username']} on instagram" + colors.ENDC)
        for key, value in self.profile_data.items():
            print(f"{key}: {value}")

    def download_profile_picture(self) -> None:
        time.sleep(random.uniform(*self.download_delay))
        self._download_file(self.profile_data["profile_pic_url"], self.output_path / "profile_pic.jpg")

    def _download_file(self, url: str, destination: Path) -> None:
        response = self._get(url)
        destination.write_bytes(response.content)
