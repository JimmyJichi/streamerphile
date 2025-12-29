#!/usr/bin/env python3
"""
Twitch Streamer Monitor Bot
Monitors Twitch streams for specific games and sends notifications via Discord.
"""

import json
import sys
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import requests
import discord
from discord import Embed
from discord import app_commands


class TwitchMonitor:
    """Monitor Twitch streams and send Discord notifications."""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize the monitor with configuration."""
        self.config_path = config_path
        self.config = self.load_config()
        
        self.twitch_token = None
        
        client_id = self.config.get("twitch_client_id", "")
        client_secret = self.config.get("twitch_client_secret", "")
        if client_id and client_secret:
            print("Attempting to get Twitch app access token...")
            self.twitch_token = self.get_app_access_token()
        
        if self.twitch_token:
            self.twitch_headers = {
                "Authorization": f"Bearer {self.twitch_token}"
            }
            if client_id:
                self.twitch_headers["Client-ID"] = client_id
        else:
            self.twitch_headers = {}
        
        self.discord_channel_id = self.config.get("discord_channel_id", "")
        self.discord_client = None
        self.notified_streams_file = "notified_streams.json"
        self.notified_streams = self.load_notified_streams()
        
    def load_config(self) -> Dict:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Set defaults if not present
            config.setdefault("max_viewers", 20)
            config.setdefault("min_viewers", 0)
            config.setdefault("max_followers", None)
            config.setdefault("min_followers", 0)
            config.setdefault("game_ids", [])
            config.setdefault("required_tags", [])
            config.setdefault("exclude_tags", [])
            config.setdefault("ignored_channels", [])
            config.setdefault("languages", [])
            config.setdefault("affiliate_or_partner_only", False)
            config.setdefault("search_interval_minutes", 30)
            config.setdefault("twitch_client_id", "")
            config.setdefault("twitch_client_secret", "")
            config.setdefault("discord_bot_token", "")
            config.setdefault("discord_channel_id", "")
            config.setdefault("debug", False)
            
            return config
        except FileNotFoundError:
            print(f"Error: {self.config_path} not found!")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {self.config_path}: {e}")
            sys.exit(1)
    
    def save_config(self):
        """Save configuration to JSON file."""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def load_notified_streams(self) -> set:
        """Load notified streams from file."""
        try:
            with open(self.notified_streams_file, 'r') as f:
                data = json.load(f)
                return set(data.get("notified_streams", []))
        except FileNotFoundError:
            return set()
        except json.JSONDecodeError as e:
            print(f"Warning: Error reading {self.notified_streams_file}: {e}")
            print("Starting with empty notified streams list.")
            return set()
        except Exception as e:
            print(f"Warning: Error loading notified streams: {e}")
            return set()
    
    def save_notified_streams(self):
        """Save notified streams to file."""
        try:
            data = {
                "notified_streams": list(self.notified_streams)
            }
            with open(self.notified_streams_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Error saving notified streams: {e}")
    
    def debug_print(self, *args, **kwargs):
        """Print debug messages only if debug is enabled in config."""
        if self.config.get("debug", False):
            print(*args, **kwargs)
    
    def get_app_access_token(self) -> Optional[str]:
        """Get an app access token using Client Credentials flow."""
        client_id = self.config.get("twitch_client_id", "")
        client_secret = self.config.get("twitch_client_secret", "")
        
        if not client_id or not client_secret:
            print("Error: twitch_client_id and twitch_client_secret are required to get an app access token")
            return None
        
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials"
        }
        
        try:
            response = requests.post(url, params=params)
            response.raise_for_status()
            data = response.json()
            token = data.get("access_token")
            
            if token:
                self.twitch_token = token
                self.twitch_headers = {
                    "Authorization": f"Bearer {token}"
                }
                if client_id:
                    self.twitch_headers["Client-ID"] = client_id
                print("Successfully obtained Twitch app access token")
                return token
            else:
                print("Error: No access token in response")
                return None
        except requests.exceptions.HTTPError as e:
            print(f"Error getting app access token: {e}")
            if e.response.status_code == 400:
                print("Invalid client_id or client_secret. Please check your credentials.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error getting app access token: {e}")
            return None
    
    def validate_and_refresh_token(self) -> bool:
        """Validate the current token and refresh if needed."""
        if not self.twitch_headers:
            return False
        
        url = "https://id.twitch.tv/oauth2/validate"
        try:
            response = requests.get(url, headers=self.twitch_headers)
            if response.status_code == 200:
                return True
            elif response.status_code == 401:
                print("Token expired or invalid. Attempting to refresh...")
                return self.get_app_access_token() is not None
        except requests.exceptions.RequestException:
            pass
        
        return self.get_app_access_token() is not None
    
    def search_games(self, query: str) -> List[Dict]:
        """Search for games on Twitch by name."""
        if not self.twitch_headers:
            print("Error: Twitch authentication not configured. Please set twitch_client_id and twitch_client_secret in config.json")
            return []
        
        url = "https://api.twitch.tv/helix/games"
        params = {"name": query}
        
        try:
            response = requests.get(url, headers=self.twitch_headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                if self.validate_and_refresh_token():
                    try:
                        response = requests.get(url, headers=self.twitch_headers, params=params)
                        response.raise_for_status()
                        data = response.json()
                        return data.get("data", [])
                    except requests.exceptions.RequestException:
                        pass
                print("Error: Invalid Twitch token. Attempting to refresh...")
            else:
                print(f"Error searching games: {e}")
            return []
        except requests.exceptions.RequestException as e:
            print(f"Error searching games: {e}")
            return []
    
    def get_streams(self, game_ids: List[str], languages: Optional[List[str]] = None) -> List[Dict]:
        """Get active streams for given game IDs, fetching all pages.
        
        Args:
            game_ids: List of game IDs to fetch streams for
            languages: Optional list of language codes to filter by (e.g., ["en", "es"])
                      If None or empty, no language filtering is applied
        """
        if not game_ids:
            self.debug_print("[DEBUG] No game IDs provided to get_streams")
            return []
        
        if not self.twitch_headers:
            print("Error: Twitch authentication not configured. Please set twitch_client_id and twitch_client_secret in config.json")
            return []
        
        self.debug_print(f"[DEBUG] Fetching streams for {len(game_ids)} game ID(s): {game_ids}")
        if languages:
            self.debug_print(f"[DEBUG] Filtering by languages: {languages}")
        url = "https://api.twitch.tv/helix/streams"
        all_streams = []
        seen_stream_ids = set()
        
        # Twitch API allows up to 100 game_ids per request
        # Pass game_ids as multiple query parameters
        for i in range(0, len(game_ids), 100):
            batch = game_ids[i:i+100]
            # Create list of tuples for multiple game_id parameters
            params = [("game_id", gid) for gid in batch]
            # Add language parameters if specified
            if languages:
                params.extend([("language", lang) for lang in languages])
            # Add first parameter to get up to 100 results per page
            params.append(("first", "100"))
            
            cursor = None
            page_num = 1
            
            while True:
                try:
                    # Add cursor to params if we have one (for pagination)
                    current_params = params.copy()
                    if cursor:
                        current_params.append(("after", cursor))
                    
                    self.debug_print(f"[DEBUG] Making API request for batch of {len(batch)} game(s), page {page_num}")
                    response = requests.get(url, headers=self.twitch_headers, params=current_params)
                    response.raise_for_status()
                    data = response.json()
                    batch_streams = data.get("data", [])
                    self.debug_print(f"[DEBUG] API returned {len(batch_streams)} stream(s) for page {page_num}")
                    
                    # For some reason sometimes there are duplicates in the results. Deduplicate streams before adding
                    for stream in batch_streams:
                        stream_id = f"{stream.get('user_id')}_{stream.get('id')}"
                        if stream_id not in seen_stream_ids:
                            seen_stream_ids.add(stream_id)
                            all_streams.append(stream)
                        else:
                            self.debug_print(f"[DEBUG]   Duplicate stream detected: {stream.get('user_name')} (ID: {stream_id})")
                    
                    # Check for next page
                    pagination = data.get("pagination", {})
                    cursor = pagination.get("cursor")
                    
                    if not cursor:
                        self.debug_print(f"[DEBUG] No more pages for this batch (total {page_num} page(s))")
                        break
                    
                    page_num += 1
                    
                except requests.exceptions.HTTPError as e:
                    self.debug_print(f"[DEBUG] HTTP Error: {e.response.status_code} - {e}")
                    if e.response.status_code == 401:
                        self.debug_print("[DEBUG] Token expired, attempting to refresh...")
                        if self.validate_and_refresh_token():
                            try:
                                self.debug_print("[DEBUG] Retrying request with new token...")
                                current_params = params.copy()
                                if cursor:
                                    current_params.append(("after", cursor))
                                response = requests.get(url, headers=self.twitch_headers, params=current_params)
                                response.raise_for_status()
                                data = response.json()
                                batch_streams = data.get("data", [])
                                self.debug_print(f"[DEBUG] Retry successful: API returned {len(batch_streams)} stream(s)")
                                
                                # Deduplicate streams before adding (same logic as above)
                                for stream in batch_streams:
                                    stream_id = f"{stream.get('user_id')}_{stream.get('id')}"
                                    if stream_id not in seen_stream_ids:
                                        seen_stream_ids.add(stream_id)
                                        all_streams.append(stream)
                                    else:
                                        self.debug_print(f"[DEBUG]   Duplicate stream detected: {stream.get('user_name')} (ID: {stream_id})")
                                
                                # Check for next page after retry
                                pagination = data.get("pagination", {})
                                cursor = pagination.get("cursor")
                                if not cursor:
                                    break
                                page_num += 1
                                continue
                            except requests.exceptions.RequestException as retry_e:
                                self.debug_print(f"[DEBUG] Retry failed: {retry_e}")
                                pass
                        print("Error: Invalid Twitch token. Attempting to refresh...")
                    else:
                        print(f"Error fetching streams: {e}")
                    break
                except requests.exceptions.RequestException as e:
                    self.debug_print(f"[DEBUG] Request exception: {e}")
                    print(f"Error fetching streams: {e}")
                    break
        
        self.debug_print(f"[DEBUG] Total streams fetched from API: {len(all_streams)}")
        return all_streams
    
    def filter_streams(self, streams: List[Dict]) -> Tuple[List[Dict], Dict[str, int]]:
        """Filter streams based on viewer count, tags, language, and follower count.
        
        Returns:
            A tuple of (filtered_streams, follower_counts) where:
            - filtered_streams: List of streams that passed all filters
            - follower_counts: Dictionary mapping user_id to follower count
        """
        min_viewers = self.config["min_viewers"]
        max_viewers = self.config["max_viewers"]
        min_followers = self.config.get("min_followers", 0)
        max_followers = self.config.get("max_followers")
        required_tags = self.config.get("required_tags", [])
        exclude_tags = self.config.get("exclude_tags", [])
        ignored_channels = self.config.get("ignored_channels", [])
        languages = self.config.get("languages", [])
        affiliate_or_partner_only = self.config.get("affiliate_or_partner_only", False)
        
        self.debug_print(f"[DEBUG] Filtering {len(streams)} stream(s) with criteria:")
        self.debug_print(f"[DEBUG]   - Min viewers: {min_viewers}")
        self.debug_print(f"[DEBUG]   - Max viewers: {max_viewers}")
        self.debug_print(f"[DEBUG]   - Min followers: {min_followers}")
        self.debug_print(f"[DEBUG]   - Max followers: {max_followers if max_followers is not None else 'No limit'}")
        self.debug_print(f"[DEBUG]   - Required tags: {required_tags}")
        self.debug_print(f"[DEBUG]   - Exclude tags: {exclude_tags}")
        self.debug_print(f"[DEBUG]   - Ignored channels: {ignored_channels}")
        self.debug_print(f"[DEBUG]   - Languages: {languages if languages else 'Any (no filter)'}")
        self.debug_print(f"[DEBUG]   - Affiliate or partner only: {affiliate_or_partner_only}")
        
        filtered_out_by_viewers_min = 0
        filtered_out_by_viewers_max = 0
        filtered_out_by_followers_min = 0
        filtered_out_by_followers_max = 0
        filtered_out_by_tags = 0
        filtered_out_by_exclude_tags = 0
        filtered_out_by_ignored_channels = 0
        filtered_out_by_affiliate_partner = 0
        
        # First pass: Apply all filters EXCEPT follower count
        # This reduces the number of API calls needed for follower counts
        pre_filtered_streams = []
        for stream in streams:
            viewer_count = stream.get("viewer_count", 0)
            user_name = stream.get("user_name", "Unknown")
            user_id = stream.get("user_id", "")
            
            if ignored_channels:
                if user_name.lower() in [ch.lower() for ch in ignored_channels] or \
                   user_id in ignored_channels:
                    filtered_out_by_ignored_channels += 1
                    self.debug_print(f"[DEBUG]   Stream '{user_name}' filtered out: channel is in ignored list")
                    continue
            
            if viewer_count < min_viewers:
                filtered_out_by_viewers_min += 1
                self.debug_print(f"[DEBUG]   Stream '{user_name}' filtered out: {viewer_count} viewers < {min_viewers} min")
                continue
            if viewer_count > max_viewers:
                filtered_out_by_viewers_max += 1
                self.debug_print(f"[DEBUG]   Stream '{user_name}' filtered out: {viewer_count} viewers > {max_viewers} max")
                continue
            
            stream_tags = stream.get("tags", [])
            
            # I don't know why this is necessary as stream_tags should never be None, 
            # but sometimes it is and the program hangs if it's not checked
            if required_tags and stream_tags is None:
                filtered_out_by_tags += 1
                self.debug_print(f"[DEBUG]   Stream '{user_name}' filtered out: no tags")
                continue
            if required_tags and stream_tags is not None:
                if not all(tag in stream_tags for tag in required_tags):
                    filtered_out_by_tags += 1
                    self.debug_print(f"[DEBUG]   Stream '{user_name}' filtered out: missing required tags")
                    self.debug_print(f"[DEBUG]     Stream tags: {stream_tags}")
                    self.debug_print(f"[DEBUG]     Required tags: {required_tags}")
                    continue
            if exclude_tags and stream_tags is not None:
                if any(tag in stream_tags for tag in exclude_tags):
                    filtered_out_by_exclude_tags += 1
                    self.debug_print(f"[DEBUG]   Stream '{user_name}' filtered out: has excluded tags")
                    self.debug_print(f"[DEBUG]     Stream tags: {stream_tags}")
                    self.debug_print(f"[DEBUG]     Excluded tags: {exclude_tags}")
                    continue
            
            # Stream passed all non-follower filters
            pre_filtered_streams.append(stream)
        
        self.debug_print(f"[DEBUG] After first pass (non-follower filters): {len(pre_filtered_streams)} stream(s) remaining")
        
        follower_counts = {}
        broadcaster_types = {}
        unique_user_ids = set()
        for stream in pre_filtered_streams:
            user_id = stream.get("user_id", "")
            if user_id:
                unique_user_ids.add(user_id)
        
        if unique_user_ids:
            # Always fetch follower counts
            self.debug_print(f"[DEBUG] Fetching follower counts for {len(unique_user_ids)} unique user(s)...")
            for user_id in unique_user_ids:
                follower_count = self.get_follower_count(user_id)
                if follower_count is not None:
                    follower_counts[user_id] = follower_count
                    self.debug_print(f"[DEBUG]   User ID {user_id}: {follower_count} followers")
                else:
                    self.debug_print(f"[DEBUG]   User ID {user_id}: Could not fetch follower count")
            
            # Fetch broadcaster types if affiliate_or_partner_only filter is enabled
            if affiliate_or_partner_only:
                self.debug_print(f"[DEBUG] Fetching broadcaster types for {len(unique_user_ids)} unique user(s)...")
                broadcaster_types = self.get_broadcaster_types_batch(list(unique_user_ids))
                # Log any user IDs that weren't found
                for user_id in unique_user_ids:
                    if user_id not in broadcaster_types:
                        self.debug_print(f"[DEBUG]   User ID {user_id}: Could not fetch broadcaster type")
        
        # Second pass: Filter by follower count and affiliate/partner status
        filtered = []
        for stream in pre_filtered_streams:
            user_name = stream.get("user_name", "Unknown")
            user_id = stream.get("user_id", "")
            viewer_count = stream.get("viewer_count", 0)
            
            # Filter by affiliate/partner status
            if affiliate_or_partner_only:
                broadcaster_type = broadcaster_types.get(user_id)
                if broadcaster_type is None:
                    filtered_out_by_affiliate_partner += 1
                    self.debug_print(f"[DEBUG]   Stream '{user_name}' filtered out: Could not determine broadcaster type")
                    continue
                if broadcaster_type not in ["affiliate", "partner"]:
                    filtered_out_by_affiliate_partner += 1
                    self.debug_print(f"[DEBUG]   Stream '{user_name}' filtered out: broadcaster_type is '{broadcaster_type}' (not affiliate or partner)")
                    continue
            
            if min_followers > 0 or max_followers is not None:
                follower_count = follower_counts.get(user_id)
                if follower_count is None:
                    self.debug_print(f"[DEBUG]   Stream '{user_name}': Could not determine follower count, skipping follower filter")
                else:
                    if follower_count < min_followers:
                        filtered_out_by_followers_min += 1
                        self.debug_print(f"[DEBUG]   Stream '{user_name}' filtered out: {follower_count} followers < {min_followers} min")
                        continue
                    if max_followers is not None and follower_count > max_followers:
                        filtered_out_by_followers_max += 1
                        self.debug_print(f"[DEBUG]   Stream '{user_name}' filtered out: {follower_count} followers > {max_followers} max")
                        continue
            
            debug_msg = f"[DEBUG]   Stream '{user_name}' passed filters: {viewer_count} viewers"
            follower_count = follower_counts.get(user_id)
            if follower_count is not None:
                debug_msg += f", {follower_count} followers"
            if affiliate_or_partner_only:
                broadcaster_type = broadcaster_types.get(user_id)
                if broadcaster_type is not None:
                    debug_msg += f", broadcaster_type: {broadcaster_type}"
            self.debug_print(debug_msg)
            filtered.append(stream)
        
        self.debug_print(f"[DEBUG] Filtering results:")
        self.debug_print(f"[DEBUG]   - Total streams: {len(streams)}")
        self.debug_print(f"[DEBUG]   - Filtered out (min viewers): {filtered_out_by_viewers_min}")
        self.debug_print(f"[DEBUG]   - Filtered out (max viewers): {filtered_out_by_viewers_max}")
        if min_followers > 0 or max_followers is not None:
            self.debug_print(f"[DEBUG]   - Filtered out (min followers): {filtered_out_by_followers_min}")
            self.debug_print(f"[DEBUG]   - Filtered out (max followers): {filtered_out_by_followers_max}")
        self.debug_print(f"[DEBUG]   - Filtered out (required tags): {filtered_out_by_tags}")
        self.debug_print(f"[DEBUG]   - Filtered out (excluded tags): {filtered_out_by_exclude_tags}")
        self.debug_print(f"[DEBUG]   - Filtered out (ignored channels): {filtered_out_by_ignored_channels}")
        if affiliate_or_partner_only:
            self.debug_print(f"[DEBUG]   - Filtered out (affiliate/partner only): {filtered_out_by_affiliate_partner}")
        self.debug_print(f"[DEBUG]   - Passed filters: {len(filtered)}")
        
        return filtered, follower_counts
    
    def get_follower_count(self, user_id: str) -> Optional[int]:
        """Get follower count for a user ID."""
        if not self.twitch_headers or not user_id:
            return None
        
        url = "https://api.twitch.tv/helix/channels/followers"
        params = {"broadcaster_id": user_id, "first": 1}  # We only need the total, so fetch 1 result
        
        try:
            response = requests.get(url, headers=self.twitch_headers, params=params)
            if response.status_code == 200:
                data = response.json()
                total = data.get("total", 0)
                return total
            elif response.status_code == 401:
                if self.validate_and_refresh_token():
                    try:
                        response = requests.get(url, headers=self.twitch_headers, params=params)
                        if response.status_code == 200:
                            data = response.json()
                            return data.get("total", 0)
                    except requests.exceptions.RequestException:
                        pass
        except requests.exceptions.RequestException:
            pass
        
        return None
    
    def get_broadcaster_type(self, user_id: str) -> Optional[str]:
        """Get broadcaster type (partner, affiliate, or empty string) for a user ID.
        
        Note: For multiple user IDs, use get_broadcaster_types_batch() instead.
        """
        if not self.twitch_headers or not user_id:
            return None
        
        url = "https://api.twitch.tv/helix/users"
        params = {"id": user_id}
        
        try:
            response = requests.get(url, headers=self.twitch_headers, params=params)
            if response.status_code == 200:
                data = response.json()
                users = data.get("data", [])
                if users:
                    broadcaster_type = users[0].get("broadcaster_type", "")
                    return broadcaster_type
            elif response.status_code == 401:
                if self.validate_and_refresh_token():
                    try:
                        response = requests.get(url, headers=self.twitch_headers, params=params)
                        if response.status_code == 200:
                            data = response.json()
                            users = data.get("data", [])
                            if users:
                                broadcaster_type = users[0].get("broadcaster_type", "")
                                return broadcaster_type
                    except requests.exceptions.RequestException:
                        pass
        except requests.exceptions.RequestException:
            pass
        
        return None
    
    def get_broadcaster_types_batch(self, user_ids: List[str]) -> Dict[str, str]:
        """Get broadcaster types for multiple user IDs in batches (up to 100 per request).
        
        Args:
            user_ids: List of user IDs to fetch broadcaster types for
            
        Returns:
            Dictionary mapping user_id to broadcaster_type (empty string if not found or error)
        """
        if not self.twitch_headers or not user_ids:
            return {}
        
        url = "https://api.twitch.tv/helix/users"
        broadcaster_types = {}
        
        # Twitch API allows up to 100 user IDs per request
        for i in range(0, len(user_ids), 100):
            batch = user_ids[i:i+100]
            params = [("id", uid) for uid in batch]
            
            try:
                self.debug_print(f"[DEBUG] Fetching broadcaster types for batch of {len(batch)} user(s)...")
                response = requests.get(url, headers=self.twitch_headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    users = data.get("data", [])
                    for user in users:
                        user_id = user.get("id", "")
                        broadcaster_type = user.get("broadcaster_type", "")
                        broadcaster_types[user_id] = broadcaster_type
                        self.debug_print(f"[DEBUG]   User ID {user_id}: broadcaster_type = '{broadcaster_type}'")
                elif response.status_code == 401:
                    if self.validate_and_refresh_token():
                        try:
                            response = requests.get(url, headers=self.twitch_headers, params=params)
                            if response.status_code == 200:
                                data = response.json()
                                users = data.get("data", [])
                                for user in users:
                                    user_id = user.get("id", "")
                                    broadcaster_type = user.get("broadcaster_type", "")
                                    broadcaster_types[user_id] = broadcaster_type
                                    self.debug_print(f"[DEBUG]   User ID {user_id}: broadcaster_type = '{broadcaster_type}'")
                        except requests.exceptions.RequestException as e:
                            self.debug_print(f"[DEBUG] Error fetching broadcaster types batch: {e}")
            except requests.exceptions.RequestException as e:
                self.debug_print(f"[DEBUG] Error fetching broadcaster types batch: {e}")
        
        return broadcaster_types
    
    async def format_streams_embed(self, streams: List[Dict], follower_counts: Optional[Dict[str, int]] = None) -> List[Embed]:
        """Format streams as Discord embeds, one per game, split if >10 streams per game.
        
        Args:
            streams: List of stream dictionaries to format
            follower_counts: Optional dictionary mapping user_id to follower count.
                           If not provided, will fetch follower counts for all unique users.
        """
        # Group streams by game
        streams_by_game = {}
        for stream in streams:
            game_name = stream.get("game_name", "Unknown")
            if game_name not in streams_by_game:
                streams_by_game[game_name] = []
            streams_by_game[game_name].append(stream)
        
        # Use provided follower counts, or fetch if not provided
        if follower_counts is None:
            follower_counts = {}
            user_ids = set()
            for stream in streams:
                user_id = stream.get("user_id")
                if user_id:
                    user_ids.add(user_id)
            
            # Fetch follower counts in parallel
            if user_ids:
                loop = asyncio.get_event_loop()
                tasks = [
                    (user_id, loop.run_in_executor(None, self.get_follower_count, user_id))
                    for user_id in user_ids
                ]
                
                # Wait for all tasks to complete
                results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
                
                # Map results back to user IDs
                for (user_id, _), result in zip(tasks, results):
                    if isinstance(result, Exception):
                        continue
                    if result is not None:
                        follower_counts[user_id] = result
        
        embeds = []
        
        for game_name, game_streams in streams_by_game.items():
            # Split into chunks of 10 streams per embed
            max_streams_per_embed = 10
            total_embeds = (len(game_streams) + max_streams_per_embed - 1) // max_streams_per_embed
            
            for embed_index in range(total_embeds):
                start_idx = embed_index * max_streams_per_embed
                end_idx = min(start_idx + max_streams_per_embed, len(game_streams))
                chunk_streams = game_streams[start_idx:end_idx]
                
                embed = Embed(
                    title=game_name,
                    color=0x9146FF
                )
                
                # Add each streamer as a field
                for stream in chunk_streams:
                    user_name = stream.get("user_name", "Unknown")
                    user_id = stream.get("user_id", "")
                    title = stream.get("title", "No title")
                    viewer_count = stream.get("viewer_count", 0)
                    url = f"https://www.twitch.tv/{user_name}"
                    
                    # Format field name with follower count
                    follower_count = follower_counts.get(user_id)
                    if follower_count is not None:
                        field_name = f"{user_name} ({follower_count} followers)"
                    else:
                        field_name = user_name
                    
                    field_value = f"[**{title}**]({url}) (Viewers: {viewer_count})"
                    
                    if len(field_value) > 1024:
                        field_value = field_value[:1020] + "..."
                    
                    embed.add_field(
                        name=field_name,
                        value=field_value,
                        inline=False
                    )
                
                # Add footer if multiple embeds for this game
                if total_embeds > 1:
                    embed.set_footer(text=f"Page {embed_index + 1} of {total_embeds}")
                
                embeds.append(embed)
        
        return embeds
    
    async def send_discord_notification(self, content=None, embed=None) -> bool:
        """Send a notification via Discord."""
        if not self.discord_client or self.discord_client.is_closed():
            print("Error: Discord bot not initialized or closed. Check your discord_bot_token in config.json")
            return False
        
        if not self.discord_channel_id:
            print("Error: Discord channel ID not configured. Check your discord_channel_id in config.json")
            return False
        
        try:
            channel = await self.discord_client.fetch_channel(int(self.discord_channel_id))
            if embed:
                await channel.send(embed=embed)
            elif content:
                await channel.send(content=content)
            return True
        except discord.errors.NotFound:
            print(f"Error: Discord channel with ID {self.discord_channel_id} not found")
            return False
        except discord.errors.Forbidden:
            print(f"Error: Bot doesn't have permission to send messages to channel {self.discord_channel_id}")
            return False
        except Exception as e:
            print(f"Error sending Discord message: {e}")
            return False
    
    def get_stream_id(self, stream: Dict) -> str:
        """Generate a unique ID for a stream."""
        return f"{stream.get('user_id')}_{stream.get('id')}"
    
    async def check_and_notify(self):
        """Check for new streams and send notifications."""
        if not self.config["game_ids"]:
            print("No games to monitor. Use the interactive menu to add games.")
            return
        
        self.debug_print(f"\n[DEBUG] ===== Starting stream check =====")
        print(f"Checking streams for {len(self.config['game_ids'])} game(s)...")
        self.debug_print(f"[DEBUG] Game IDs being monitored: {self.config['game_ids']}")
        self.debug_print(f"[DEBUG] Currently tracking {len(self.notified_streams)} already-notified stream(s)")
        
        languages = self.config.get("languages", [])
        streams = self.get_streams(self.config["game_ids"], languages if languages else None)
        self.debug_print(f"[DEBUG] Raw streams from API: {len(streams)}")
        
        if streams:
            self.debug_print(f"[DEBUG] Sample stream data (first stream):")
            sample = streams[0]
            self.debug_print(f"[DEBUG]   - User: {sample.get('user_name')}")
            self.debug_print(f"[DEBUG]   - Game: {sample.get('game_name')}")
            self.debug_print(f"[DEBUG]   - Viewers: {sample.get('viewer_count')}")
            self.debug_print(f"[DEBUG]   - Language: {sample.get('language', 'Unknown')}")
            self.debug_print(f"[DEBUG]   - Tags: {sample.get('tags', [])}")
        
        filtered_streams, follower_counts = self.filter_streams(streams)
        self.debug_print(f"[DEBUG] Streams after filtering: {len(filtered_streams)}")
        
        new_streams = []
        already_notified = []
        for stream in filtered_streams:
            stream_id = self.get_stream_id(stream)
            if stream_id not in self.notified_streams:
                new_streams.append(stream)
            else:
                already_notified.append(stream.get('user_name'))
        
        if already_notified:
            self.debug_print(f"[DEBUG] Already notified streams: {already_notified}")
        
        self.debug_print(f"[DEBUG] New streams (not yet notified): {len(new_streams)}")
        
        if new_streams:
            print(f"Found {len(new_streams)} new stream(s) matching criteria!")
            
            embeds = await self.format_streams_embed(new_streams, follower_counts)
            
            # Discord rate limit: 5 messages per 5 seconds
            # Sleep if sending more than 5 messages
            if len(embeds) > 5:
                print(f"Sending {len(embeds)} embeds with rate limiting...")
            
            sent_count = 0
            for i, embed in enumerate(embeds):
                if i > 0 and i % 5 == 0:
                    print("Rate limiting: sleeping for 5 seconds...")
                    await asyncio.sleep(5)
                
                if await self.send_discord_notification(embed=embed):
                    sent_count += 1
                else:
                    print(f"Failed to send embed {i + 1} of {len(embeds)}")
            
            if sent_count == len(embeds):
                for stream in new_streams:
                    self.notified_streams.add(self.get_stream_id(stream))
                self.save_notified_streams()
                print(f"All {sent_count} embed(s) sent successfully for {len(new_streams)} stream(s)")
            else:
                print(f"Warning: Only {sent_count} of {len(embeds)} embed(s) were sent successfully")
        else:
            print("No new streams found.")
            if filtered_streams:
                self.debug_print(f"[DEBUG] Note: {len(filtered_streams)} stream(s) matched filters but were already notified")
            elif streams:
                self.debug_print(f"[DEBUG] Note: {len(streams)} stream(s) found but none matched the filter criteria")
            else:
                self.debug_print(f"[DEBUG] Note: No streams found for the monitored game IDs")
        
        self.debug_print(f"[DEBUG] ===== Stream check complete =====\n")
    
    def interactive_menu(self):
        """Interactive menu for managing games."""
        while True:
            print("\n" + "="*50)
            print("Twitch Streamer Monitor - Interactive Menu")
            print("="*50)
            print("1. Search for games")
            print("2. View watched games")
            print("3. Remove a game from watch list")
            print("4. Start monitoring")
            print("5. Exit")
            print("="*50)
            
            choice = input("\nEnter your choice (1-5): ").strip()
            
            if choice == "1":
                self.search_and_add_game()
            elif choice == "2":
                self.view_watched_games()
            elif choice == "3":
                self.remove_game()
            elif choice == "4":
                self.start_monitoring()
            elif choice == "5":
                print("Exiting...")
                break
            else:
                print("Invalid choice. Please try again.")
    
    def search_and_add_game(self):
        """Search for games and add one to the watch list."""
        query = input("\nEnter game name to search: ").strip()
        if not query:
            print("No query entered.")
            return
        
        print(f"\nSearching for '{query}'...")
        games = self.search_games(query)
        
        if not games:
            print("No games found.")
            return
        
        print(f"\nFound {len(games)} game(s):")
        for i, game in enumerate(games, 1):
            print(f"{i}. {game.get('name')} (ID: {game.get('id')})")
        
        try:
            selection = input(f"\nSelect a game to add (1-{len(games)}) or 0 to cancel: ").strip()
            if selection == "0":
                return
            
            index = int(selection) - 1
            if 0 <= index < len(games):
                game_id = games[index]["id"]
                game_name = games[index]["name"]
                
                if game_id in self.config["game_ids"]:
                    print(f"'{game_name}' is already in the watch list.")
                else:
                    self.config["game_ids"].append(game_id)
                    self.save_config()
                    print(f"Added '{game_name}' (ID: {game_id}) to watch list.")
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    def view_watched_games(self):
        """Display currently watched games."""
        game_ids = self.config.get("game_ids", [])
        if not game_ids:
            print("\nNo games in watch list.")
            return
        
        print(f"\nCurrently watching {len(game_ids)} game(s):")
        for i, game_id in enumerate(game_ids, 1):
            if not self.twitch_headers:
                print(f"{i}. Game ID: {game_id} (Token not configured)")
                continue
            
            url = "https://api.twitch.tv/helix/games"
            params = {"id": game_id}
            try:
                response = requests.get(url, headers=self.twitch_headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("data"):
                        game_name = data["data"][0].get("name", "Unknown")
                        print(f"{i}. {game_name} (ID: {game_id})")
                    else:
                        print(f"{i}. Unknown game (ID: {game_id})")
                elif response.status_code == 401:
                    if self.validate_and_refresh_token():
                        try:
                            response = requests.get(url, headers=self.twitch_headers, params=params)
                            if response.status_code == 200:
                                data = response.json()
                                if data.get("data"):
                                    game_name = data["data"][0].get("name", "Unknown")
                                    print(f"{i}. {game_name} (ID: {game_id})")
                                else:
                                    print(f"{i}. Unknown game (ID: {game_id})")
                            else:
                                print(f"{i}. Game ID: {game_id}")
                        except requests.exceptions.RequestException:
                            print(f"{i}. Game ID: {game_id}")
                    else:
                        print(f"{i}. Game ID: {game_id} (Authentication failed)")
                else:
                    print(f"{i}. Game ID: {game_id}")
            except Exception as e:
                print(f"{i}. Game ID: {game_id} (Error fetching name: {e})")
    
    def remove_game(self):
        """Remove a game from the watch list."""
        game_ids = self.config.get("game_ids", [])
        if not game_ids:
            print("\nNo games in watch list.")
            return
        
        self.view_watched_games()
        try:
            selection = input(f"\nSelect a game to remove (1-{len(game_ids)}) or 0 to cancel: ").strip()
            if selection == "0":
                return
            
            index = int(selection) - 1
            if 0 <= index < len(game_ids):
                removed_id = game_ids.pop(index)
                self.save_config()
                print(f"Removed game ID {removed_id} from watch list.")
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    def start_monitoring(self):
        """Start the monitoring loop."""
        if not self.config["game_ids"]:
            print("\nNo games to monitor. Please add games first.")
            return
        
        if not self.twitch_headers:
            print("\nError: Twitch authentication not configured.")
            print("Please ensure twitch_client_id and twitch_client_secret are set in config.json")
            return
        
        if not self.config.get("discord_bot_token") or not self.config.get("discord_channel_id"):
            print("\nError: Discord bot token or channel ID not configured in config.json")
            return
        
        interval = self.config["search_interval_minutes"] * 60
        print(f"\nStarting monitoring...")
        print(f"Checking every {self.config['search_interval_minutes']} minutes")
        print(f"Viewer range: {self.config['min_viewers']} - {self.config['max_viewers']}")
        min_followers = self.config.get("min_followers", 0)
        max_followers = self.config.get("max_followers")
        if min_followers > 0 or max_followers is not None:
            max_followers_str = str(max_followers) if max_followers is not None else "∞"
            print(f"Follower range: {min_followers} - {max_followers_str}")
        print("Press Ctrl+C to stop\n")
        
        intents = discord.Intents.default()
        self.discord_client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.discord_client)
        
        @self.tree.command(name="ignore", description="Add a Twitch channel to the ignored list")
        async def ignore_command(interaction: discord.Interaction, channel: str):
            """Add a channel to the ignored_channels list."""
            ignored_channels = self.config.get("ignored_channels", [])
            
            channel_lower = channel.lower().strip()
            
            if any(ch.lower() == channel_lower for ch in ignored_channels):
                await interaction.response.send_message(
                    f"❌ Channel `{channel}` is already in the ignored list.",
                    ephemeral=True
                )
                return
            
            ignored_channels.append(channel)
            self.config["ignored_channels"] = ignored_channels
            self.save_config()
            self.config = self.load_config()
            
            await interaction.response.send_message(
                f"✅ Added `{channel}` to the ignored channels list.",
                ephemeral=True
            )
            print(f"Channel '{channel}' added to ignored list via Discord command by {interaction.user}")
        
        async def main():
            """Main async function to run Discord client and monitoring."""
            monitoring_task = None
            
            async def monitoring_loop():
                """Main monitoring loop that runs after Discord client is ready."""
                await self.discord_client.wait_until_ready()
                print("Discord bot is ready!")
                
                # Sync commands
                # try:
                #     synced = await self.tree.sync()
                #     print(f"Synced {len(synced)} command(s)")
                # except Exception as e:
                #     print(f"Failed to sync commands: {e}")
                
                try:
                    while not self.discord_client.is_closed():
                        await self.check_and_notify()
                        print(f"\nNext check in {self.config['search_interval_minutes']} minutes...")
                        await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    pass
            
            # Set up the monitoring loop as a background task
            @self.discord_client.event
            async def on_ready():
                nonlocal monitoring_task
                monitoring_task = asyncio.create_task(monitoring_loop())
            
            try:
                await self.discord_client.start(self.config["discord_bot_token"])
            except KeyboardInterrupt:
                print("\n\nMonitoring stopped by user.")
            finally:
                if monitoring_task:
                    monitoring_task.cancel()
                    try:
                        await monitoring_task
                    except asyncio.CancelledError:
                        pass
                if not self.discord_client.is_closed():
                    await self.discord_client.close()
        
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user.")


def main():
    """Main entry point."""
    monitor = TwitchMonitor()
    monitor.interactive_menu()


if __name__ == "__main__":
    main()

