#!/usr/bin/env python3
"""
Script to fetch JSON data from wplace pumpkin tiles endpoint and serve filtered results.
"""

import requests
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Set, List
from flask import Flask, render_template_string, request, jsonify
import threading
import webbrowser


def fetch_pumpkin_data(url: str = "https://wplace.samuelscheit.com/tiles/pumpkin.json") -> Dict[str, Any]:
    """
    Fetch JSON data from the pumpkin tiles endpoint.
    
    Args:
        url (str): The URL to fetch data from
        
    Returns:
        Dict[str, Any]: The JSON response data
        
    Raises:
        requests.exceptions.RequestException: If the request fails
        json.JSONDecodeError: If the response is not valid JSON
    """
    try:
        print(f"Fetching data from: {url}")
        
        # Make the GET request
        response = requests.get(url, timeout=30)
        
        # Raise an exception for bad status codes
        response.raise_for_status()
        
        # Parse JSON response
        data = response.json()
        
        print(f"Successfully fetched {len(data)} pumpkins")
        return data
        
    except requests.exceptions.Timeout:
        print("Error: Request timed out")
        raise
    except requests.exceptions.ConnectionError:
        print("Error: Failed to connect to the server")
        raise
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP {response.status_code} - {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON response - {e}")
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise


def read_existing_ids(filename: str = "data.json") -> Set[int]:
    """
    Read existing pumpkin IDs from data.json file.
    
    Args:
        filename (str): The filename to read from
        
    Returns:
        Set[int]: Set of existing pumpkin IDs
    """
    try:
        if not os.path.exists(filename):
            print(f"File {filename} not found, starting with empty list")
            return set()
            
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Handle different possible formats
        if isinstance(data, list):
            existing_ids = set(data)
        elif isinstance(data, dict):
            # Check if it has a "claimed" key (our format)
            if "claimed" in data and isinstance(data["claimed"], list):
                existing_ids = set(data["claimed"])
            else:
                # Fallback to using dict keys as IDs
                existing_ids = set(int(k) for k in data.keys() if k.isdigit())
        else:
            print(f"Unexpected data format in {filename}")
            return set()
            
        print(f"Found {len(existing_ids)} existing pumpkin IDs")
        return existing_ids
        
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return set()


def filter_new_pumpkins(pumpkin_data: Dict[str, Any], existing_ids: Set[int]) -> Dict[str, Any]:
    """
    Filter pumpkins to only include ones we don't already have.
    
    Args:
        pumpkin_data (Dict[str, Any]): All pumpkin data
        existing_ids (Set[int]): Set of existing pumpkin IDs
        
    Returns:
        Dict[str, Any]: Filtered pumpkin data
    """
    new_pumpkins = {}
    
    for pumpkin_id, pumpkin_info in pumpkin_data.items():
        try:
            id_num = int(pumpkin_id)
            if id_num not in existing_ids:
                new_pumpkins[pumpkin_id] = pumpkin_info
        except ValueError:
            continue
            
    print(f"Found {len(new_pumpkins)} new pumpkins")
    return new_pumpkins


def filter_recent_pumpkins(pumpkin_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter pumpkins to only include ones found within the current hour.
    
    Args:
        pumpkin_data (Dict[str, Any]): Pumpkin data to filter
        
    Returns:
        Dict[str, Any]: Filtered pumpkin data
    """
    now = datetime.now(timezone.utc)
    current_hour_start = now.replace(minute=0, second=0, microsecond=0)
    
    recent_pumpkins = {}
    
    for pumpkin_id, pumpkin_info in pumpkin_data.items():
        try:
            found_at = datetime.fromisoformat(pumpkin_info['foundAt'].replace('Z', '+00:00'))
            if found_at >= current_hour_start:
                recent_pumpkins[pumpkin_id] = pumpkin_info
        except (KeyError, ValueError) as e:
            print(f"Error parsing timestamp for pumpkin {pumpkin_id}: {e}")
            continue
            
    print(f"Found {len(recent_pumpkins)} pumpkins from the current hour")
    return recent_pumpkins


def generate_pumpkin_link(lat: float, lng: float) -> str:
    """
    Generate a wplace.live link for a pumpkin location.
    
    Args:
        lat (float): Latitude
        lng (float): Longitude
        
    Returns:
        str: The formatted link
    """
    return f"https://wplace.live/?lat={lat}&lng={lng}&zoom=14"


def create_web_app(initial_pumpkin_data: Dict[str, Any]) -> Flask:
    """
    Create a Flask web application to display the filtered pumpkins.
    
    Args:
        initial_pumpkin_data (Dict[str, Any]): The initial pumpkin data from API
        
    Returns:
        Flask: The Flask application
    """
    app = Flask(__name__)
    
    # Store the fetched pumpkin data globally for the app
    app.pumpkin_data = initial_pumpkin_data
    
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>New Pumpkins Found This Hour</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 20px; 
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .input-section-wrapper {
                display: flex;
                gap: 15px;
                margin-bottom: 30px;
            }
            .input-section {
                flex: 2;
                background-color: #f9f9f9;
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 20px;
            }
            .sidebar {
                flex: 1;
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 20px;
                max-height: 400px;
                overflow-y: auto;
            }
            .links-panel {
                flex: 1;
                background-color: #fff3cd;
                border: 2px solid #ffc107;
                border-radius: 8px;
                padding: 20px;
                max-height: 400px;
                overflow-y: auto;
            }
            h1 { 
                color: #ff6b35; 
                text-align: center;
                margin-bottom: 30px;
            }

            .input-label {
                font-weight: bold;
                margin-bottom: 10px;
                color: #333;
            }
            .data-input {
                width: 100%;
                min-height: 150px;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-family: monospace;
                font-size: 12px;
                resize: vertical;
            }
            .update-button {
                background-color: #ff6b35;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-weight: bold;
                margin-top: 10px;
                transition: background-color 0.3s;
            }
            .update-button:hover {
                background-color: #d55200;
            }
            .update-button:disabled {
                background-color: #ccc;
                cursor: not-allowed;
            }
            .status-message {
                margin-top: 10px;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            .status-success {
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .status-error {
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            .pumpkin-results {
                border-top: 3px solid #ff6b35;
                padding-top: 20px;
            }
            .pumpkin-item {
                background-color: #fff8f0;
                border: 2px solid #ff6b35;
                border-radius: 8px;
                padding: 15px;
                margin: 10px 0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .pumpkin-info {
                flex-grow: 1;
            }
            .pumpkin-id {
                font-weight: bold;
                font-size: 1.2em;
                color: #d55200;
            }
            .pumpkin-details {
                color: #666;
                font-size: 0.9em;
                margin-top: 5px;
            }
            .pumpkin-link {
                background-color: #ff6b35;
                color: white;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                transition: background-color 0.3s;
            }
            .pumpkin-link:hover {
                background-color: #d55200;
            }
            .no-pumpkins {
                text-align: center;
                color: #666;
                font-style: italic;
                padding: 40px;
            }
            .refresh-info {
                text-align: center;
                color: #666;
                margin-top: 20px;
                font-size: 0.9em;
            }
            .sidebar-title {
                font-weight: bold;
                font-size: 1.1em;
                color: #495057;
                margin-bottom: 15px;
                text-align: center;
            }
            .missing-list {
                background: white;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 15px;
                font-family: monospace;
                font-size: 12px;
                white-space: pre-wrap;
                max-height: 300px;
                overflow-y: auto;
                margin-bottom: 15px;
            }
            .copy-button {
                width: 100%;
                background-color: #007bff;
                color: white;
                padding: 8px 12px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: bold;
                transition: background-color 0.3s;
            }
            .copy-button:hover {
                background-color: #0056b3;
            }
            .copy-success {
                background-color: #28a745 !important;
            }
            .links-title {
                font-weight: bold;
                font-size: 1.1em;
                color: #856404;
                margin-bottom: 15px;
                text-align: center;
            }
            .links-list {
                background: white;
                border: 1px solid #ffc107;
                border-radius: 4px;
                padding: 15px;
                max-height: 300px;
                overflow-y: auto;
                margin-bottom: 15px;
            }
            .pumpkin-link-item {
                margin-bottom: 8px;
                padding: 8px;
                background-color: #fff8e1;
                border-radius: 4px;
                border-left: 3px solid #ffc107;
            }
            .pumpkin-link-item a {
                text-decoration: none;
                color: #856404;
                font-weight: bold;
                font-size: 0.9em;
            }
            .pumpkin-link-item a:hover {
                color: #533f03;
                text-decoration: underline;
            }
            .copy-links-button {
                width: 100%;
                background-color: #ffc107;
                color: #212529;
                padding: 8px 12px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: bold;
                transition: background-color 0.3s;
            }
            .copy-links-button:hover {
                background-color: #e0a800;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎃 New Pumpkins Found This Hour</h1>
            
            <div class="progress-section" style="background-color: #e8f5e8; border: 2px solid #28a745; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                <div style="font-weight: bold; font-size: 1.2em; color: #155724; margin-bottom: 15px;">📊 Pumpkin Progress</div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px;">
                    <div style="background: white; padding: 15px; border-radius: 6px; text-align: center; border: 1px solid #28a745;">
                        <div style="font-size: 1.5em; font-weight: bold; color: #ff6b35;" id="totalPumpkins">{{ total_pumpkins }}</div>
                        <div style="color: #666; font-size: 0.9em;">Total in Game</div>
                    </div>
                    <div style="background: white; padding: 15px; border-radius: 6px; text-align: center; border: 1px solid #28a745;">
                        <div style="font-size: 1.5em; font-weight: bold; color: #6f42c1;" id="apiPumpkins">{{ api_pumpkins }}</div>
                        <div style="color: #666; font-size: 0.9em;">Discovered</div>
                    </div>
                    <div style="background: white; padding: 15px; border-radius: 6px; text-align: center; border: 1px solid #28a745;">
                        <div style="font-size: 1.5em; font-weight: bold; color: #28a745;" id="claimedPumpkins">{{ claimed_pumpkins }}</div>
                        <div style="color: #666; font-size: 0.9em;">Already Claimed</div>
                    </div>
                    <div style="background: white; padding: 15px; border-radius: 6px; text-align: center; border: 1px solid #28a745;">
                        <div style="font-size: 1.5em; font-weight: bold; color: #dc3545;" id="pumpkinsLeft">{{ pumpkins_left }}</div>
                        <div style="color: #666; font-size: 0.9em;">Pumpkins Left</div>
                    </div>
                    <div style="background: white; padding: 15px; border-radius: 6px; text-align: center; border: 1px solid #28a745;">
                        <div style="font-size: 1.5em; font-weight: bold; color: #17a2b8;" id="newThisHour">{{ new_this_hour }}</div>
                        <div style="color: #666; font-size: 0.9em;">New This Hour</div>
                    </div>
                </div>
                <div style="margin-top: 15px; text-align: center; color: #666;">
                    <div id="progressText">Real Progress: {{ claimed_pumpkins }}/{{ total_pumpkins }} ({{ real_progress_percent }}% complete)</div>
                    <div style="font-size: 0.85em; color: #888; margin-top: 5px;" id="apiProgressText">API Progress: {{ claimed_pumpkins }}/{{ api_pumpkins }} ({{ api_progress_percent }}% of discovered)</div>
                </div>
            </div>
            
            <div class="input-section-wrapper">
                <div class="input-section">
                <div class="input-label">📋 Update Claimed Pumpkins (Paste data.json content):</div>
                <textarea id="dataInput" class="data-input" placeholder='Paste your data.json content here, e.g.:
{
  "claimed": [1, 2, 3, 4, 5, ...]
}'></textarea>
                <button id="updateButton" class="update-button" onclick="updatePumpkins()">Update Results</button>
                <div id="statusMessage" class="status-message" style="display: none;"></div>
                </div>
                
                <div class="sidebar">
                    <div class="sidebar-title">📋 Missing Pumpkins</div>
                    <div class="missing-list" id="missingList">{{ missing_pumpkins_text }}</div>
                    <button class="copy-button" id="copyButton" onclick="copyMissingList()">Copy Missing List</button>
                    <div style="margin-top: 15px; font-size: 0.85em; color: #666; text-align: center;">
                        <div>Missing from API: <span id="missingFromApi">{{ missing_from_api_count }}</span></div>
                        <div>Available but unclaimed: <span id="availableUnclaimed">{{ available_unclaimed_count }}</span></div>
                    </div>
                </div>
                
                <div class="links-panel">
                    <div class="links-title">🔗 Recent Unclaimed Links</div>
                    <div class="missing-list" id="linksList">{{ unclaimed_links_text }}</div>
                    <button class="copy-links-button" id="copyLinksButton" onclick="copyUnclaimedLinks()">Copy Recent Links</button>
                    <div style="margin-top: 15px; font-size: 0.85em; color: #856404; text-align: center;">
                        <div>Recent links (this hour): <span id="availableLinksCount">{{ recent_unclaimed_count }}</span></div>
                    </div>
                </div>
            </div>
            
            <div class="pumpkin-results">
                <div id="pumpkinResults">
                    {% if pumpkins %}
                        {% for id, info in pumpkins.items() %}
                        <div class="pumpkin-item">
                            <div class="pumpkin-info">
                                <div class="pumpkin-id">Pumpkin {{ id }}</div>
                                <div class="pumpkin-details">
                                    Found at: {{ info.foundAt }}<br>
                                    Coordinates: {{ "%.4f"|format(info.lat) }}, {{ "%.4f"|format(info.lng) }}<br>
                                    Tile: {{ info.tileX }}, {{ info.tileY }} | Offset: {{ info.offsetX }}, {{ info.offsetY }}
                                </div>
                            </div>
                            <a href="{{ generate_link(info.lat, info.lng) }}" target="_blank" class="pumpkin-link">
                                View Location
                            </a>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div class="no-pumpkins">
                            No new pumpkins found in the current hour. 🕐
                        </div>
                    {% endif %}
                </div>
                
                <div class="refresh-info">
                    Last updated: <span id="lastUpdate">{{ current_time }}</span><br>
                    Total new pumpkins this hour: <span id="pumpkinCount">{{ pumpkin_count }}</span>
                </div>
            </div>
        </div>
        
        <script>
            // Load initial data from data.json if available
            window.onload = function() {
                fetch('/get_initial_data')
                    .then(response => response.json())
                    .then(data => {
                        if (data.success && data.data) {
                            document.getElementById('dataInput').value = JSON.stringify(data.data, null, 2);
                        }
                    })
                    .catch(err => console.log('Could not load initial data:', err));
            };
            
            function updatePumpkins() {
                const dataInput = document.getElementById('dataInput').value.trim();
                const updateButton = document.getElementById('updateButton');
                const statusMessage = document.getElementById('statusMessage');
                
                if (!dataInput) {
                    showStatus('Please enter data.json content', 'error');
                    return;
                }
                
                updateButton.disabled = true;
                updateButton.textContent = 'Updating...';
                
                fetch('/update_pumpkins', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({data: dataInput})
                })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        document.getElementById('pumpkinResults').innerHTML = result.html;
                        document.getElementById('lastUpdate').textContent = result.timestamp;
                        document.getElementById('pumpkinCount').textContent = result.count;
                        
                        // Update progress statistics
                        document.getElementById('totalPumpkins').textContent = result.totalPumpkins;
                        document.getElementById('apiPumpkins').textContent = result.apiPumpkins;
                        document.getElementById('claimedPumpkins').textContent = result.claimedPumpkins;
                        document.getElementById('pumpkinsLeft').textContent = result.pumpkinsLeft;
                        document.getElementById('newThisHour').textContent = result.count;
                        
                        // Update progress text
                        const realProgressPercent = result.totalPumpkins > 0 ? ((result.claimedPumpkins / result.totalPumpkins) * 100).toFixed(1) : 0;
                        const apiProgressPercent = result.apiPumpkins > 0 ? ((result.claimedPumpkins / result.apiPumpkins) * 100).toFixed(1) : 0;
                        document.getElementById('progressText').textContent = `Real Progress: ${result.claimedPumpkins}/${result.totalPumpkins} (${realProgressPercent}% complete)`;
                        document.getElementById('apiProgressText').textContent = `API Progress: ${result.claimedPumpkins}/${result.apiPumpkins} (${apiProgressPercent}% of discovered)`;
                        
                        // Update sidebar
                        document.getElementById('missingList').textContent = result.missingPumpkinsText;
                        document.getElementById('missingFromApi').textContent = result.missingFromApiCount;
                        document.getElementById('availableUnclaimed').textContent = result.availableUnclaimedCount;
                        
                        // Update links panel
                        document.getElementById('linksList').textContent = result.unclaimedLinksText;
                        document.getElementById('availableLinksCount').textContent = result.recentUnclaimedCount;
                        
                        showStatus(`Updated successfully! Found ${result.count} new pumpkins.`, 'success');
                    } else {
                        showStatus('Error: ' + result.error, 'error');
                    }
                })
                .catch(err => {
                    showStatus('Network error: ' + err.message, 'error');
                })
                .finally(() => {
                    updateButton.disabled = false;
                    updateButton.textContent = 'Update Results';
                });
            }
            
            function showStatus(message, type) {
                const statusEl = document.getElementById('statusMessage');
                statusEl.textContent = message;
                statusEl.className = 'status-message status-' + type;
                statusEl.style.display = 'block';
                
                // Hide after 5 seconds
                setTimeout(() => {
                    statusEl.style.display = 'none';
                }, 5000);
            }
            
            function copyMissingList() {
                const missingList = document.getElementById('missingList');
                const button = document.getElementById('copyButton');
                
                // Select and copy the text
                if (navigator.clipboard && window.isSecureContext) {
                    navigator.clipboard.writeText(missingList.textContent).then(() => {
                        button.textContent = 'Copied!';
                        button.classList.add('copy-success');
                        setTimeout(() => {
                            button.textContent = 'Copy Missing List';
                            button.classList.remove('copy-success');
                        }, 2000);
                    });
                } else {
                    // Fallback for older browsers
                    const textArea = document.createElement('textarea');
                    textArea.value = missingList.textContent;
                    document.body.appendChild(textArea);
                    textArea.select();
                    document.execCommand('copy');
                    document.body.removeChild(textArea);
                    
                    button.textContent = 'Copied!';
                    button.classList.add('copy-success');
                    setTimeout(() => {
                        button.textContent = 'Copy Missing List';
                        button.classList.remove('copy-success');
                    }, 2000);
                }
            }
            
            function copyUnclaimedLinks() {
                const linksList = document.getElementById('linksList');
                const button = document.getElementById('copyLinksButton');
                
                // Get the plain text content
                const linksText = linksList.textContent;
                
                // Copy the text
                if (navigator.clipboard && window.isSecureContext) {
                    navigator.clipboard.writeText(linksText).then(() => {
                        button.textContent = 'Copied!';
                        button.style.backgroundColor = '#28a745';
                        setTimeout(() => {
                            button.textContent = 'Copy All Links';
                            button.style.backgroundColor = '#ffc107';
                        }, 2000);
                    });
                } else {
                    // Fallback for older browsers
                    const textArea = document.createElement('textarea');
                    textArea.value = linksText;
                    document.body.appendChild(textArea);
                    textArea.select();
                    document.execCommand('copy');
                    document.body.removeChild(textArea);
                    
                    button.textContent = 'Copied!';
                    button.style.backgroundColor = '#28a745';
                    setTimeout(() => {
                        button.textContent = 'Copy All Links';
                        button.style.backgroundColor = '#ffc107';
                    }, 2000);
                }
            }
        </script>
    </body>
    </html>
    """
    
    @app.route('/')
    def index():
        # Get initial filtered data
        try:
            existing_ids = read_existing_ids()
            new_pumpkins = filter_new_pumpkins(app.pumpkin_data, existing_ids)
            recent_pumpkins = filter_recent_pumpkins(new_pumpkins)
        except:
            recent_pumpkins = {}
            existing_ids = set()
            
        # Calculate progress statistics
        api_pumpkins = len(app.pumpkin_data)  # Pumpkins currently discovered/available in API
        total_pumpkins = 100  # Total pumpkins that exist in the game
        claimed_pumpkins = len(existing_ids)
        pumpkins_left = total_pumpkins - claimed_pumpkins
        api_progress_percent = round((claimed_pumpkins / api_pumpkins * 100), 1) if api_pumpkins > 0 else 0
        real_progress_percent = round((claimed_pumpkins / total_pumpkins * 100), 1)
        
        # Generate missing pumpkins list
        all_possible_ids = set(range(1, total_pumpkins + 1))
        api_pumpkin_ids = set(int(pid) for pid in app.pumpkin_data.keys())
        missing_from_api = sorted(all_possible_ids - api_pumpkin_ids)
        available_unclaimed = sorted(api_pumpkin_ids - existing_ids)
        
        missing_pumpkins_text = "Missing from API:\n" + ", ".join(map(str, missing_from_api))
        missing_pumpkins_text += "\n\nAvailable but unclaimed:\n" + ", ".join(map(str, available_unclaimed))
        
        missing_from_api_count = len(missing_from_api)
        available_unclaimed_count = len(available_unclaimed)
        
        # Generate unclaimed links text (filtered for current hour)
        unclaimed_links_text = ""
        recent_unclaimed_count = 0
        for pumpkin_id in available_unclaimed:
            pumpkin_info = app.pumpkin_data.get(str(pumpkin_id))
            if pumpkin_info:
                # Check if this pumpkin was found within the current hour
                try:
                    found_at = datetime.fromisoformat(pumpkin_info['foundAt'].replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    current_hour_start = now.replace(minute=0, second=0, microsecond=0)
                    
                    if found_at >= current_hour_start:
                        link = generate_pumpkin_link(pumpkin_info['lat'], pumpkin_info['lng'])
                        unclaimed_links_text += f"{pumpkin_id}: {link}\n"
                        recent_unclaimed_count += 1
                except (KeyError, ValueError):
                    continue
            
        return render_template_string(
            html_template,
            pumpkins=recent_pumpkins,
            generate_link=generate_pumpkin_link,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            pumpkin_count=len(recent_pumpkins),
            total_pumpkins=total_pumpkins,
            api_pumpkins=api_pumpkins,
            claimed_pumpkins=claimed_pumpkins,
            pumpkins_left=pumpkins_left,
            new_this_hour=len(recent_pumpkins),
            api_progress_percent=api_progress_percent,
            real_progress_percent=real_progress_percent,
            missing_pumpkins_text=missing_pumpkins_text,
            missing_from_api_count=missing_from_api_count,
            available_unclaimed_count=available_unclaimed_count,
            unclaimed_links_text=unclaimed_links_text,
            recent_unclaimed_count=recent_unclaimed_count
        )
    
    @app.route('/get_initial_data')
    def get_initial_data():
        """Get the current data.json content for the input field."""
        try:
            if os.path.exists("data.json"):
                with open("data.json", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return jsonify({"success": True, "data": data})
            else:
                return jsonify({"success": False, "error": "data.json not found"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    @app.route('/update_pumpkins', methods=['POST'])
    def update_pumpkins():
        """Update the pumpkin results based on new claimed data."""
        try:
            request_data = request.get_json()
            input_data = request_data.get('data', '')
            
            # Parse the input JSON
            try:
                claimed_data = json.loads(input_data)
            except json.JSONDecodeError as e:
                return jsonify({"success": False, "error": f"Invalid JSON: {str(e)}"})
            
            # Extract claimed IDs
            if isinstance(claimed_data, dict) and "claimed" in claimed_data:
                existing_ids = set(claimed_data["claimed"])
            elif isinstance(claimed_data, list):
                existing_ids = set(claimed_data)
            else:
                return jsonify({"success": False, "error": "Expected format: {'claimed': [1,2,3...]} or [1,2,3...]"})
            
            # Filter pumpkins
            new_pumpkins = filter_new_pumpkins(app.pumpkin_data, existing_ids)
            recent_pumpkins = filter_recent_pumpkins(new_pumpkins)
            
            # Generate HTML for the results
            html_parts = []
            if recent_pumpkins:
                for pumpkin_id, info in recent_pumpkins.items():
                    link = generate_pumpkin_link(info['lat'], info['lng'])
                    html_parts.append(f'''
                    <div class="pumpkin-item">
                        <div class="pumpkin-info">
                            <div class="pumpkin-id">Pumpkin {pumpkin_id}</div>
                            <div class="pumpkin-details">
                                Found at: {info['foundAt']}<br>
                                Coordinates: {info['lat']:.4f}, {info['lng']:.4f}<br>
                                Tile: {info['tileX']}, {info['tileY']} | Offset: {info['offsetX']}, {info['offsetY']}
                            </div>
                        </div>
                        <a href="{link}" target="_blank" class="pumpkin-link">
                            View Location
                        </a>
                    </div>
                    ''')
            else:
                html_parts.append('''
                <div class="no-pumpkins">
                    No new pumpkins found in the current hour. 🕐
                </div>
                ''')
            
            # Calculate progress statistics
            api_pumpkins = len(app.pumpkin_data)  # Pumpkins currently discovered/available in API
            total_pumpkins = 100  # Total pumpkins that exist in the game
            claimed_pumpkins = len(existing_ids)
            pumpkins_left = total_pumpkins - claimed_pumpkins
            
            # Generate missing pumpkins list
            all_possible_ids = set(range(1, total_pumpkins + 1))
            api_pumpkin_ids = set(int(pid) for pid in app.pumpkin_data.keys())
            missing_from_api = sorted(all_possible_ids - api_pumpkin_ids)
            available_unclaimed = sorted(api_pumpkin_ids - existing_ids)
            
            missing_pumpkins_text = "Missing from API:\n" + ", ".join(map(str, missing_from_api))
            missing_pumpkins_text += "\n\nAvailable but unclaimed:\n" + ", ".join(map(str, available_unclaimed))
            
            # Generate unclaimed links text (filtered for current hour)
            unclaimed_links_text = ""
            recent_unclaimed_count = 0
            for pumpkin_id in available_unclaimed:
                pumpkin_info = app.pumpkin_data.get(str(pumpkin_id))
                if pumpkin_info:
                    # Check if this pumpkin was found within the current hour
                    try:
                        found_at = datetime.fromisoformat(pumpkin_info['foundAt'].replace('Z', '+00:00'))
                        now = datetime.now(timezone.utc)
                        current_hour_start = now.replace(minute=0, second=0, microsecond=0)
                        
                        if found_at >= current_hour_start:
                            link = generate_pumpkin_link(pumpkin_info['lat'], pumpkin_info['lng'])
                            unclaimed_links_text += f"{pumpkin_id}: {link}\n"
                            recent_unclaimed_count += 1
                    except (KeyError, ValueError):
                        continue
            
            return jsonify({
                "success": True,
                "html": ''.join(html_parts),
                "count": len(recent_pumpkins),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "totalPumpkins": total_pumpkins,
                "apiPumpkins": api_pumpkins,
                "claimedPumpkins": claimed_pumpkins,
                "pumpkinsLeft": pumpkins_left,
                "missingPumpkinsText": missing_pumpkins_text,
                "missingFromApiCount": len(missing_from_api),
                "availableUnclaimedCount": len(available_unclaimed),
                "unclaimedLinksText": unclaimed_links_text,
                "recentUnclaimedCount": recent_unclaimed_count
            })
            
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    return app


def save_data_to_file(data: Dict[str, Any], filename: str = "pumpkin_data.json") -> None:
    """
    Save the fetched data to a JSON file.
    
    Args:
        data (Dict[str, Any]): The data to save
        filename (str): The filename to save to
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data saved to {filename}")
    except Exception as e:
        print(f"Error saving data to file: {e}")
        raise


def open_browser():
    """Open the browser after a short delay."""
    threading.Timer(1.5, lambda: webbrowser.open('http://127.0.0.1:5000')).start()


def main():
    """Main function to execute the script."""
    try:
        print("=== Pumpkin Tracker ===\n")
        
        # Step 1: Get the list of pumpkins
        print("Step 1: Fetching pumpkin data...")
        pumpkin_data = fetch_pumpkin_data()
        
        # Step 2: Read existing IDs from data.json
        print("\nStep 2: Reading existing pumpkin IDs...")
        existing_ids = read_existing_ids()
        
        # Step 3: Filter to pumpkins we don't have
        print("\nStep 3: Filtering to new pumpkins...")
        new_pumpkins = filter_new_pumpkins(pumpkin_data, existing_ids)
        
        # Step 4: Filter to pumpkins from the current hour
        print("\nStep 4: Filtering to recent pumpkins...")
        recent_pumpkins = filter_recent_pumpkins(new_pumpkins)
        
        # Step 5: Calculate and display pumpkins left to get
        api_pumpkins = len(pumpkin_data)  # Pumpkins currently discovered/available in API
        total_pumpkins = 100  # Total pumpkins that exist in the game
        claimed_pumpkins = len(existing_ids)
        pumpkins_left = total_pumpkins - claimed_pumpkins
        undiscovered_pumpkins = total_pumpkins - api_pumpkins
        
        print(f"\n📊 Pumpkin Progress:")
        print(f"   Total pumpkins in game: {total_pumpkins}")
        print(f"   Pumpkins discovered (API): {api_pumpkins}")
        print(f"   Pumpkins not yet discovered: {undiscovered_pumpkins}")
        print(f"   Pumpkins already claimed: {claimed_pumpkins}")
        print(f"   Pumpkins left to get: {pumpkins_left}")
        print(f"   Real progress: {claimed_pumpkins}/{total_pumpkins} ({round((claimed_pumpkins/total_pumpkins*100), 1)}%)")
        print(f"   API progress: {claimed_pumpkins}/{api_pumpkins} ({round((claimed_pumpkins/api_pumpkins*100), 1) if api_pumpkins > 0 else 0}%)")
        print(f"   New pumpkins found this hour: {len(recent_pumpkins)}")
        
        # Save all fetched data for reference
        save_data_to_file(pumpkin_data, "all_pumpkins.json")
        save_data_to_file(recent_pumpkins, "recent_new_pumpkins.json")
        
        # Step 6: Serve website
        print(f"\nStep 6: Starting web server...")
        app = create_web_app(pumpkin_data)
        
        print("\n🎃 Pumpkin Tracker is running!")
        print("📍 Open your browser to: http://127.0.0.1:5000")
        print("⏹️  Press Ctrl+C to stop the server")
        
        # Open browser automatically
        open_browser()
        
        # Run the Flask app
        app.run(host='127.0.0.1', port=5000, debug=False)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
        return 0
    except Exception as e:
        print(f"Script failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())