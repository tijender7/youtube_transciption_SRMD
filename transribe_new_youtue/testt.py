import os
import re
import time
import requests
from pytube import Playlist
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from urllib.parse import urlparse, parse_qs

def get_safe_filename(title):
    """Sanitize the video title to create a safe filename."""
    return re.sub(r'[<>:"/\\|?*]', '', title).replace(' ', '_')

def get_video_id(video_url):
    """Extracts video ID from YouTube URL."""
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
    """Fetches transcript for a given video ID."""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        return transcript_list.find_transcript(['en']).fetch()
    except NoTranscriptFound:
        try:
            return transcript_list.find_generated_transcript(['en']).fetch()
        except NoTranscriptFound:
            print(f"No transcript available for video ID: {video_id}")
            return None
    except TranscriptsDisabled:
        print(f"Transcripts are disabled for video ID: {video_id}")
        return None
    except Exception as e:
        print(f"Error fetching transcript for video ID {video_id}: {e}")
        return None

def save_transcript(transcript, title, output_dir):
    """Saves the transcript to a text file."""
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
    """Extracts videos from a playlist and processes them for transcripts."""
    try:
        playlist = Playlist(playlist_url)
        playlist._video_regex = re.compile(r"\"url\":\"(/watch\?v=[\w-]*)")

        if not playlist.video_urls:
            print("No videos found in the playlist. Please check the URL or playlist privacy settings.")
            return

        if not output_dir:
            output_dir = get_safe_filename(playlist.title)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        print(f"\nFound {len(playlist.video_urls)} videos in the playlist.")
        for video_url in playlist.video_urls:
            process_video(video_url, output_dir)
            time.sleep(1)  # Pause to prevent rate limiting
    except Exception as e:
        print(f"Error processing playlist: {e}")

if __name__ == "__main__":
    playlist_url = input("Enter the YouTube playlist URL: ").strip()
    if not playlist_url:
        print("No URL provided. Exiting.")
    else:
        output_dir = input("Enter the directory to save transcripts (press Enter to use the playlist name): ").strip()
        download_playlist_transcripts(playlist_url, output_dir if output_dir else None)
