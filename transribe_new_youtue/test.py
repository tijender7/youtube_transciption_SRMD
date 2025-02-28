import os
import re
from pytube import Playlist

def get_safe_filename(title):
    """Sanitize the playlist title to create a safe directory name."""
    return re.sub(r'[<>:"/\\|?*]', '', title).replace(' ', '_')

def extract_video_urls(playlist_url):
    """Extract video URLs from the given YouTube playlist URL."""
    try:
        playlist = Playlist(playlist_url)
        # Fix for potential empty video list issue
        playlist._video_regex = re.compile(r"\"url\":\"(/watch\?v=[\w-]*)")
        video_urls = playlist.video_urls
        if not video_urls:
            print("No videos found in the playlist. Please check the URL or playlist privacy settings.")
            return []
        return video_urls
    except Exception as e:
        print(f"Error processing playlist: {e}")
        return []

def main():
    playlist_url = input("Enter the YouTube playlist URL: ").strip()
    if not playlist_url:
        print("No URL provided. Exiting.")
        return

    output_dir = input("Enter the directory to save transcripts (press Enter to use the playlist name): ").strip()
    
    # Extract video URLs
    video_urls = extract_video_urls(playlist_url)
    if not video_urls:
        return

    # If no directory is specified, use the playlist title
    if not output_dir:
        try:
            playlist = Playlist(playlist_url)
            output_dir = get_safe_filename(playlist.title)
        except Exception as e:
            print(f"Error retrieving playlist title: {e}")
            output_dir = "Playlist"

    # Create the directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"\nFound {len(video_urls)} videos in the playlist:")
    for url in video_urls:
        print(url)

    print(f"\nVideo URLs have been extracted and can be processed further. Files will be saved in: {output_dir}")

if __name__ == "__main__":
    main()
