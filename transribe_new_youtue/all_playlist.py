from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import re

def scroll_down(driver, pause_time=2):
    """Scrolls down the page until no new content is loaded."""
    last_height = driver.execute_script("return document.documentElement.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(pause_time)
        new_height = driver.execute_script("return document.documentElement.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def get_all_playlist_links(channel_url):
    """Uses Selenium to load the full channel playlists page and extracts all playlist URLs."""
    # Set up headless Chrome
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    
    driver = webdriver.Chrome(options=options)
    driver.get(channel_url)
    
    # Give the page some time to load initial content
    time.sleep(3)
    # Scroll until the page is fully loaded
    scroll_down(driver, pause_time=2)
    
    # Get the fully loaded page source
    html = driver.page_source
    driver.quit()
    
    # Parse the page source with BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)
    
    playlist_links = set()
    # Look for links that contain both "/watch?v=" and "list=" which indicate playlists
    for link in links:
        href = link["href"]
        if "/watch?v=" in href and "list=" in href:
            match = re.search(r"list=([\w-]+)", href)
            if match:
                playlist_id = match.group(1)
                playlist_links.add(f"https://www.youtube.com/playlist?list={playlist_id}")
                
    return list(playlist_links)

if __name__ == "__main__":
    # Channel playlists URL (you can try adding query parameters like ?view=57 or ?flow=grid if needed)
    channel_url = "https://www.youtube.com/@SRMD/playlists"
    playlists = get_all_playlist_links(channel_url)
    
    if playlists:
        print(f"Found {len(playlists)} playlists:")
        for idx, playlist in enumerate(playlists, start=1):
            print(f"{idx}. {playlist}")
    else:
        print("No playlists found or an error occurred.")
