from youtube_transcript_api import YouTubeTranscriptApi
import re
from urllib.parse import urlparse, parse_qs
import requests
import os
import time
from bs4 import BeautifulSoup
import json

def get_channel_id(url):
    """Extract channel ID from various YouTube channel URL formats"""
    try:
        if 'youtube.com/channel/' in url:
            return url.split('youtube.com/channel/')[1].split('/')[0]
        
        # For user URLs, we need to fetch the page to get channel ID
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Try to find channel ID in meta tags
            for link in soup.find_all('meta'):
                if 'content' in link.attrs:
                    content = link.attrs['content']
                    if 'channel/' in content:
                        return content.split('channel/')[1].split('/')[0]
                    if 'user/' in content:
                        return content.split('user/')[1].split('/')[0]
    except Exception as e:
        print(f"Error getting channel ID: {str(e)}")
    return None

def get_channel_videos(channel_url):
    """Get list of video URLs from channel using initial page load + AJAX requests"""
    videos = []
    try:
        # Get the initial page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # First get the channel page
        response = requests.get(channel_url + "/videos", headers=headers)
        if response.status_code != 200:
            print("Could not access channel page")
            return videos

        # Parse the initial page
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all script tags that might contain our data
        scripts = soup.find_all('script')
        
        # Extract video URLs from the page
        for script in scripts:
            if script.string and 'var ytInitialData = ' in script.string:
                data_text = script.string.split('var ytInitialData = ')[1].split(';</script>')[0]
                try:
                    data = json.loads(data_text)
                    # Navigate through the JSON structure
                    tabs = data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])
                    for tab in tabs:
                        if 'tabRenderer' in tab and tab['tabRenderer'].get('title') == 'Videos':
                            items = tab['tabRenderer']['content']['richGridRenderer']['contents']
                            for item in items:
                                if 'richItemRenderer' in item:
                                    video_data = item['richItemRenderer']['content']['videoRenderer']
                                    video_id = video_data.get('videoId')
                                    if video_id:
                                        videos.append(f"https://www.youtube.com/watch?v={video_id}")
                except Exception as e:
                    print(f"Error parsing video data: {str(e)}")
                    continue

        print(f"Found {len(videos)} videos")
        return list(set(videos))

    except Exception as e:
        print(f"Error getting channel videos: {str(e)}")
        return videos

def get_safe_filename(title):
    """Convert title to safe filename"""
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
    safe_title = safe_title.replace(' ', '_')
    return safe_title

def get_video_title(video_id):
    """Get video title using YouTube's oEmbed API"""
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        response = requests.get(oembed_url)
        if response.status_code == 200:
            return response.json()['title']
    except Exception:
        pass
    return video_id

def get_transcript(video_id):
    """Try to get transcript in any available language"""
    try:
        # First try to get all available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        print("\nAvailable transcript languages:")
        for transcript in transcript_list:
            print(f"- {transcript.language} ({'Auto-generated' if transcript.is_generated else 'Manual'})")
        
        # Try to get English transcript first
        try:
            return transcript_list.find_transcript(['en']).fetch()
        except:
            try:
                # Try to get auto-generated English
                return transcript_list.find_generated_transcript(['en']).fetch()
            except:
                pass
        
        # Try to get Hindi transcript (since the video is in Hindi)
        try:
            return transcript_list.find_transcript(['hi']).fetch()
        except:
            try:
                # Try to get auto-generated Hindi
                return transcript_list.find_generated_transcript(['hi']).fetch()
            except:
                pass
        
        # Try to get any manual transcript
        try:
            manual_transcripts = [t for t in transcript_list.manual_transcripts]
            if manual_transcripts:
                transcript = transcript_list.find_transcript([manual_transcripts[0].language_code])
                print(f"\nUsing manual transcript in {transcript.language}")
                return transcript.fetch()
        except:
            pass
        
        # If nothing else works, get the first available transcript
        try:
            available = list(transcript_list)
            if available:
                transcript = available[0]
                print(f"\nUsing available transcript in {transcript.language}")
                return transcript.fetch()
        except:
            pass
            
    except Exception as e:
        if "No transcripts were found" in str(e):
            print("\nNo transcripts available for this video")
        else:
            print(f"\nError getting transcript: {str(e)}")
    return None

def download_video_transcript(video_url, output_dir):
    """Download transcript for a single video"""
    try:
        # Get video ID
        if 'watch?v=' in video_url:
            video_id = video_url.split('watch?v=')[1].split('&')[0]
        else:
            print(f"Invalid video URL: {video_url}")
            return False

        # Get video title
        video_title = get_video_title(video_id)
        safe_title = get_safe_filename(video_title)
        print(f"\nProcessing video: {video_title}")

        # Get transcript
        transcript = get_transcript(video_id)
        if not transcript:
            print("Could not get transcript (no captions available in any language)")
            return False

        # Format transcript
        formatted_transcript = []
        for entry in transcript:
            time = f"[{int(entry['start']//60):02d}:{int(entry['start']%60):02d}]"
            formatted_transcript.append(f"{time} {entry['text']}")

        # Save to file
        filename = os.path.join(output_dir, f"{safe_title}_transcript.txt")
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(formatted_transcript))
        
        print(f"Transcript saved to: {filename}")
        return True

    except Exception as e:
        print(f"Error processing video: {str(e)}")
        return False

def process_channel():
    try:
        # Get channel URL
        print("\nPlease enter the YouTube channel URL (or 'q' to quit):")
        print("(e.g., https://www.youtube.com/@ChannelName)")
        channel_url = input("> ").strip()
        
        if channel_url.lower() in ['q', 'quit', 'exit']:
            return False
        
        if not channel_url:
            print("No URL provided. Please try again or enter 'q' to quit.")
            return True
        
        # Create output directory
        channel_name = channel_url.rstrip('/').split('/')[-1]
        output_dir = get_safe_filename(channel_name)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        print(f"\nGetting videos from channel: {channel_url}")
        videos = get_channel_videos(channel_url)
        
        if not videos:
            print("No videos found in the channel.")
            return True
        
        print(f"\nFound {len(videos)} videos. Starting transcript download...")
        
        successful = 0
        failed = 0
        
        for i, video_url in enumerate(videos, 1):
            print(f"\nProcessing video {i}/{len(videos)}")
            if download_video_transcript(video_url, output_dir):
                successful += 1
            else:
                failed += 1
            time.sleep(1)  # Add delay to avoid rate limiting
        
        print(f"\nDownload complete!")
        print(f"Successfully downloaded: {successful} transcripts")
        print(f"Failed to download: {failed} transcripts")
        print(f"Transcripts are saved in the '{output_dir}' directory")
        return True

    except Exception as e:
        print(f"\nAn unexpected error occurred: {str(e)}")
        print("Please try again with a different channel URL.")
        return True

if __name__ == "__main__":
    print("YouTube Channel Transcript Downloader")
    print("====================================")
    
    while True:
        try:
            if not process_channel():
                break
                
            while True:
                print("\nWould you like to process another channel? (yes/no)")
                response = input("> ").strip().lower()
                
                # Check if the response is actually a channel URL
                if 'youtube.com/' in response or '@' in response:
                    channel_url = response
                    break
                elif response in ['y', 'yes']:
                    break
                elif response in ['n', 'no', 'q', 'quit', 'exit']:
                    print("Goodbye!")
                    exit(0)
                else:
                    print("Please enter 'yes' or 'no' (or enter a YouTube channel URL directly)")
                    
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nAn error occurred: {str(e)}")
            print("Please try again or enter 'q' to quit.") 