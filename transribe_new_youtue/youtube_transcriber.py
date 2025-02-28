from youtube_transcript_api import YouTubeTranscriptApi
import re
from urllib.parse import urlparse, parse_qs
import requests

def get_video_id(url):
    """Extract video ID from YouTube URL"""
    # Handle different URL formats
    if 'youtu.be' in url:
        return url.split('/')[-1].split('?')[0]
    if 'youtube.com' in url:
        parsed_url = urlparse(url)
        if 'v' in parse_qs(parsed_url.query):
            return parse_qs(parsed_url.query)['v'][0]
    return None

def get_safe_filename(title):
    """Convert video title to safe filename"""
    # Remove invalid filename characters
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
    # Replace spaces with underscores
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

def process_url(url):
    """Process a single YouTube URL"""
    try:
        print(f"\nProcessing video: {url}")
        
        # Get video ID
        video_id = get_video_id(url)
        if not video_id:
            print("Error: Could not extract video ID from URL")
            return False

        # Get video title using oEmbed API
        video_title = get_video_title(video_id)
        safe_title = get_safe_filename(video_title)
        print(f"Video title: {video_title}")

        # Get transcript
        transcript = get_transcript(video_id)
        if not transcript:
            print("\nError: Could not get transcript.")
            print("This might be because:")
            print("- The video has no captions in any language")
            print("- The video is private or unavailable")
            print("- YouTube API request failed")
            return False

        # Format transcript without timestamps
        formatted_transcript = [entry['text'] for entry in transcript]

        # Save to file
        filename = f"{safe_title}_transcript.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(formatted_transcript))
        
        print(f"\nTranscript successfully saved to: {filename}")
        return True

    except Exception as e:
        print(f"\nAn unexpected error occurred: {str(e)}")
        print("Please try again with a different video.")
        return False

def download_transcript():
    while True:
        try:
            # Ask for URL
            print("\nPlease enter the YouTube video URL (or 'q' to quit):")
            url = input("> ").strip()
            
            if url.lower() in ['q', 'quit', 'exit']:
                return False
            
            if not url:
                print("No URL provided. Please try again or enter 'q' to quit.")
                continue
            
            process_url(url)
            
            # Ask if user wants to continue
            while True:
                print("\nWould you like to download another transcript? (yes/no)")
                response = input("> ").strip().lower()
                
                # Check if the response is actually a URL
                if 'youtube.com' in response or 'youtu.be' in response:
                    process_url(response)
                    break
                elif response in ['y', 'yes']:
                    break
                elif response in ['n', 'no', 'q', 'quit', 'exit']:
                    return False
                else:
                    print("Please enter 'yes' or 'no' (or enter a YouTube URL directly)")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            return False
        except Exception as e:
            print(f"\nAn error occurred: {str(e)}")
            print("Please try again or enter 'q' to quit.")

if __name__ == "__main__":
    print("YouTube Transcript Downloader")
    print("============================")
    download_transcript()
    print("\nGoodbye!") 