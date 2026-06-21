import json
import tempfile
import unittest
from pathlib import Path

from InstagramOSINT import InstagramOSINT


class FakeResponse:
    def __init__(self, text="", content=b"image"):
        self.text = text
        self.content = content

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, html):
        self.html = html
        self.urls = []

    def get(self, url, headers=None, timeout=None):
        self.urls.append(url)
        if url.endswith(".jpg"):
            return FakeResponse(content=b"jpg-data")
        return FakeResponse(text=self.html)


PROFILE_JSON = {
    "entry_data": {
        "ProfilePage": [
            {
                "graphql": {
                    "user": {
                        "username": "example",
                        "full_name": "Example User",
                        "biography": "bio",
                        "profile_pic_url_hd": "https://cdn.example/profile.jpg",
                        "is_business_account": False,
                        "connected_fb_page": None,
                        "external_url": "https://example.com",
                        "is_joined_recently": False,
                        "business_category_name": None,
                        "is_private": False,
                        "is_verified": True,
                        "edge_followed_by": {"count": 10},
                        "edge_follow": {"count": 5},
                        "edge_owner_to_timeline_media": {
                            "count": 1,
                            "edges": [
                                {
                                    "node": {
                                        "edge_media_to_caption": {"edges": []},
                                        "edge_media_to_comment": {"count": 2},
                                        "comments_disabled": False,
                                        "taken_at_timestamp": 123,
                                        "edge_liked_by": {"count": 3},
                                        "location": None,
                                        "accessibility_caption": "Alt text",
                                        "thumbnail_resources": [{"src": "https://cdn.example/thumb.jpg"}],
                                    }
                                }
                            ],
                        },
                    }
                }
            }
        ]
    }
}


def html_fixture():
    return f"""
    <html><head>
      <meta property="og:description" content="10 Followers, 5 Following, 1 Posts - See photos and videos" />
      <script type="application/ld+json">{{"name":"Example User","mainEntityofPage":{{"@id":"https://www.instagram.com/example/"}}}}</script>
      <script>window._sharedData = {json.dumps(PROFILE_JSON)};</script>
    </head></html>
    """


class InstagramOSINTTests(unittest.TestCase):
    def test_profile_parsing_and_username_cleanup(self):
        osint = InstagramOSINT("@example", session=FakeSession(html_fixture()))
        self.assertEqual(osint["Username"], "example")
        self.assertEqual(osint.profile_data["Followers"], "10")
        self.assertEqual(osint.profile_data["is_verified"], "True")

    def test_save_data_and_scrape_posts_without_changing_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            start = Path.cwd()
            osint = InstagramOSINT("example", output_dir=tmp, session=FakeSession(html_fixture()), download_delay=(0, 0))
            output_path = osint.save_data(download_profile_picture=False)
            posts = osint.scrape_posts(download_images=False)
            self.assertEqual(Path.cwd(), start)
            self.assertTrue((output_path / "data.txt").exists())
            self.assertTrue((output_path / "posts.txt").exists())
            self.assertEqual(posts[0]["Caption"], "No Caption on this post")


if __name__ == "__main__":
    unittest.main()
