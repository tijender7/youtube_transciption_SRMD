from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import re
import os
import requests
from pytube import Playlist, YouTube
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from urllib.parse import urlparse, parse_qs

#########################################
# Part 1: Extract Playlist Links via Selenium
#########################################

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
    """
    Uses Selenium to load the full channel playlists page and extracts all playlist URLs.
    Returns a list of full playlist URLs.
    """
    # Set up headless Chrome
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    
    driver = webdriver.Chrome(options=options)
    driver.get(channel_url)
    
    # Allow initial content to load
    time.sleep(3)
    # Scroll to fully load the page
    scroll_down(driver, pause_time=2)
    
    # Get the fully loaded page source
    html = driver.page_source
    driver.quit()
    
    # Parse the page source with BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)
    
    playlist_links = set()
    # Look for links that include both "/watch?v=" and "list="
    for link in links:
        href = link["href"]
        if "/watch?v=" in href and "list=" in href:
            match = re.search(r"list=([\w-]+)", href)
            if match:
                playlist_id = match.group(1)
                playlist_links.add(f"https://www.youtube.com/playlist?list={playlist_id}")
                
    return list(playlist_links)

#########################################
# Part 2: Download Transcripts for Each Playlist
#########################################

def get_safe_filename(title):
    """Sanitize the title to create a safe filename/folder name."""
    return re.sub(r'[<>:"/\\|?*]', '', title).replace(' ', '_')

def get_video_id(video_url):
    """Extracts video ID from a YouTube URL."""
    parsed_url = urlparse(video_url)
    if 'v' in parse_qs(parsed_url.query):
        return parse_qs(parsed_url.query)['v'][0]
    return None

def get_video_title(video_id):
    """Fetches video title using YouTube's oEmbed API."""
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        response = requests.get(oembed_url)
        if response.status_code == 200:
            return response.json()['title']
    except Exception:
        pass
    return video_id  # Fallback to video ID if title retrieval fails

def fetch_transcript(video_id):
    """
    Fetches transcript for a given video ID.
    Attempts manual English first, then auto-generated English.
    If unavailable, tries any available manual transcript (translating to English if possible),
    and finally falls back to the first available transcript in any language.
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        print("\nAvailable transcript languages:")
        for transcript in transcript_list:
            print(f"- {transcript.language} ({'Auto-generated' if transcript.is_generated else 'Manual'})")
        
        # Priority 1: Manual English transcript
        try:
            transcript = transcript_list.find_transcript(['en'])
            if not transcript.is_generated:
                print("\nUsing manual English transcript")
                return transcript.fetch()
        except Exception:
            pass
        
        # Priority 2: Auto-generated English transcript
        try:
            transcript = transcript_list.find_generated_transcript(['en'])
            print("\nUsing auto-generated English transcript")
            return transcript.fetch()
        except Exception:
            pass
        
        # Priority 3: Try any available manual transcript; attempt translation to English
        try:
            manual_transcripts = [t for t in transcript_list.manual_transcripts]
            if manual_transcripts:
                transcript = transcript_list.find_transcript([manual_transcripts[0].language_code])
                try:
                    translated = transcript.translate('en')
                    print(f"\nUsing translated manual transcript from {transcript.language} to English")
                    return translated.fetch()
                except Exception:
                    print(f"\nUsing original manual transcript in {transcript.language}")
                    return transcript.fetch()
        except Exception:
            pass
        
        # Priority 4: Use the first available transcript (regardless of language)
        try:
            available = list(transcript_list)
            if available:
                transcript = available[0]
                print(f"\nUsing available transcript in {transcript.language}")
                return transcript.fetch()
        except Exception:
            pass
        
        print(f"\nNo transcripts available for video ID: {video_id}")
        return None
        
    except Exception as e:
        if "No transcripts were found" in str(e):
            print(f"\nNo transcripts available for video ID: {video_id}")
        else:
            print(f"\nError fetching transcript for video ID {video_id}: {e}")
        return None

def save_transcript(transcript, title, output_dir):
    """Saves the transcript to a text file inside the specified directory."""
    safe_title = get_safe_filename(title)
    filename = os.path.join(output_dir, f"{safe_title}_transcript.txt")
    with open(filename, 'w', encoding='utf-8') as file:
        for entry in transcript:
            file.write(f"{entry['text']}\n")
    print(f"Transcript saved: {filename}")

def process_video(video_url, output_dir):
    """Processes a single video: fetches its transcript and saves it."""
    try:
        video_id = get_video_id(video_url)
        if not video_id:
            print(f"Error extracting video ID for URL: {video_url}")
            return
        
        title = get_video_title(video_id)
        print(f"\nProcessing video: {title}")
        transcript = fetch_transcript(video_id)
        if transcript:
            save_transcript(transcript, title, output_dir)
        else:
            print(f"Skipping video '{title}' due to missing transcript.")
    except Exception as e:
        print(f"Error processing video {video_url}: {e}")

def download_playlist_transcripts(playlist_url, output_dir=None):
    """
    Extracts videos from a playlist and processes them for transcripts.
    If output_dir is not specified, uses the playlist title as folder name.
    """
    try:
        playlist = Playlist(playlist_url)
        # Fix for pytube extraction issues
        playlist._video_regex = re.compile(r"\"url\":\"(/watch\?v=[\w-]*)")
        
        if not playlist.video_urls:
            print("No videos found in the playlist. Please check the URL or playlist privacy settings.")
            return

        # Use playlist title as folder name if output_dir is not provided
        if not output_dir:
            output_dir = get_safe_filename(playlist.title)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        print(f"\nFound {len(playlist.video_urls)} videos in playlist: {playlist.title}")
        for video_url in playlist.video_urls:
            process_video(video_url, output_dir)
            time.sleep(1)  # Pause briefly to prevent rate limiting
    except Exception as e:
        print(f"Error processing playlist: {e}")

#########################################
# Main: Combine Everything
#########################################

if __name__ == "__main__":
    # Step 1: Ask for the channel playlists URL
    channel_url = input("Enter the channel playlists URL (e.g., https://www.youtube.com/@SRMD/playlists): ").strip()
    if not channel_url:
        print("No channel URL provided. Exiting.")
        exit(1)

    # Extract all playlist links from the channel using Selenium
    print("\nExtracting all playlist links from the channel...")
    playlist_links = get_all_playlist_links(channel_url)
    if playlist_links:
        print(f"\nFound {len(playlist_links)} playlists:")
        for idx, pl in enumerate(playlist_links, start=1):
            print(f"{idx}. {pl}")
    else:
        print("No playlists found or an error occurred.")
        exit(1)

    # Step 2: For each playlist, download transcripts for every video
    download_choice = input("\nDownload transcripts for all playlists? (yes/no): ").strip().lower()
    if download_choice not in ['yes', 'y']:
        print("Exiting without downloading transcripts.")
        exit(0)

    # Process each playlist sequentially
    for playlist_link in playlist_links:
        print(f"\nProcessing playlist: {playlist_link}")
        download_playlist_transcripts(playlist_link)
    
    print("\nAll playlists processed.")
