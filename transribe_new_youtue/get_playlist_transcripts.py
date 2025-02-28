from youtube_transcript_api import YouTubeTranscriptApi
import requests
from bs4 import BeautifulSoup
import json
import os
import time
from urllib.parse import parse_qs, urlparse

def get_video_id(url):
    """Extract video ID from YouTube URL"""
    try:
        if 'youtu.be' in url:
            return url.split('/')[-1].split('?')[0]
        if 'youtube.com' in url:
            parsed_url = urlparse(url)
            if 'v' in parse_qs(parsed_url.query):
                return parse_qs(parsed_url.query)['v'][0]
    except Exception as e:
        print(f"Error extracting video ID: {str(e)}")
    return None

def get_safe_filename(title):
    """Convert title to safe filename"""
    return "".join(c if c.isalnum() or c in ' -_' else '_' for c in title).strip()

def get_playlist_videos(playlist_url):
    """Get all video URLs from a playlist"""
    videos = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        print(f"\nFetching videos from playlist: {playlist_url}")
        response = requests.get(playlist_url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for ytInitialData
            for script in soup.find_all('script'):
                if script.string and 'var ytInitialData = ' in script.string:
                    data_text = script.string
                    start_idx = data_text.find('var ytInitialData = ') + len('var ytInitialData = ')
                    end_idx = data_text.find(';</script>', start_idx)
                    
                    if start_idx > 0 and end_idx > 0:
                        try:
                            data = json.loads(data_text[start_idx:end_idx])
                            
                            # Try to find playlist videos
                            contents = data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])[0].get('tabRenderer', {}).get('content', {}).get('sectionListRenderer', {}).get('contents', [])[0].get('itemSectionRenderer', {}).get('contents', [])[0].get('playlistVideoListRenderer', {}).get('contents', [])
                            
                            if contents:
                                for item in contents:
                                    if 'playlistVideoRenderer' in item:
                                        video_data = item['playlistVideoRenderer']
                                        video_id = video_data.get('videoId')
                                        title = ' '.join(t.get('text', '') for t in video_data.get('title', {}).get('runs', []))
                                        
                                        if video_id:
                                            url = f"https://www.youtube.com/watch?v={video_id}"
                                            videos.append({
                                                'url': url,
                                                'id': video_id,
                                                'title': title
                                            })
                                            print(f"Found video: {title}")
                        
                        except json.JSONDecodeError as e:
                            print(f"Error parsing JSON: {str(e)}")
                            continue
            
            # If no videos found, try HTML parsing
            if not videos:
                print("\nTrying HTML parsing method...")
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '/watch?v=' in href:
                        video_id = href.split('watch?v=')[1].split('&')[0]
                        title_elem = link.find(['span', 'yt-formatted-string'], {'class': 'title'})
                        title = title_elem.text if title_elem else f"Video_{video_id}"
                        
                        url = f"https://www.youtube.com/watch?v={video_id}"
                        if url not in [v['url'] for v in videos]:
                            videos.append({
                                'url': url,
                                'id': video_id,
                                'title': title
                            })
                            print(f"Found video: {title}")
    
    except Exception as e:
        print(f"Error getting playlist videos: {str(e)}")
    
    print(f"\nFound {len(videos)} videos in playlist")
    return videos

def get_transcript(video_id):
    """Get transcript for a video"""
    try:
        # Try to get available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # First try: Manual English transcript
        try:
            transcript = transcript_list.find_transcript(['en'])
            if not transcript.is_generated:
                print("Using manual English transcript")
                return transcript.fetch()
        except:
            pass
        
        # Second try: Auto-generated English transcript
        try:
            transcript = transcript_list.find_generated_transcript(['en'])
            print("Using auto-generated English transcript")
            return transcript.fetch()
        except:
            pass
        
        # Third try: Any manual transcript translated to English
        try:
            manual_transcripts = [t for t in transcript_list.manual_transcripts]
            if manual_transcripts:
                transcript = transcript_list.find_transcript([manual_transcripts[0].language_code])
                translated = transcript.translate('en')
                print(f"Using translated transcript from {transcript.language_code} to English")
                return translated.fetch()
        except:
            pass
        
        # Last try: Any available transcript
        try:
            available = list(transcript_list)
            if available:
                transcript = available[0]
                print(f"Using transcript in {transcript.language_code}")
                return transcript.fetch()
        except:
            pass
        
    except Exception as e:
        print(f"Error getting transcript: {str(e)}")
    return None

def process_playlists():
    """Process all playlists from playlists.json"""
    try:
        # Load playlists
        with open("playlists.json", "r", encoding="utf-8") as f:
            playlists = json.load(f)
        
        print(f"\nFound {len(playlists)} playlists to process")
        
        for playlist in playlists:
            print(f"\nProcessing playlist: {playlist['title']}")
            
            # Create directory for playlist
            playlist_dir = get_safe_filename(playlist['title'])
            if not os.path.exists(playlist_dir):
                os.makedirs(playlist_dir)
            
            # Get videos
            videos = get_playlist_videos(playlist['url'])
            
            # Process each video
            for video in videos:
                print(f"\nProcessing video: {video['title']}")
                
                # Get transcript
                transcript = get_transcript(video['id'])
                if transcript:
                    # Save transcript
                    filename = os.path.join(playlist_dir, f"{get_safe_filename(video['title'])}_transcript.txt")
                    with open(filename, "w", encoding="utf-8") as f:
                        for entry in transcript:
                            f.write(f"{entry['text']}\n")
                    print(f"Saved transcript to: {filename}")
                else:
                    print("No transcript available")
                
                time.sleep(1)  # Delay to avoid rate limiting
            
            print(f"\nCompleted playlist: {playlist['title']}")
            time.sleep(2)  # Delay between playlists
        
        print("\nAll playlists processed!")
    
    except Exception as e:
        print(f"Error processing playlists: {str(e)}")

if __name__ == "__main__":
    process_playlists() 