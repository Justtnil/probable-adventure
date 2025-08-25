#!/usr/bin/env python3
"""
Backend API Testing Script for Daily Feels Mood Tracker
Tests all backend endpoints using the external URL from frontend/.env
"""

import requests
import json
import sys
from datetime import datetime, date, timedelta
import uuid

# Configuration
BASE_URL = "https://daily-feels-128.preview.emergentagent.com/api"
HEADERS = {"Content-Type": "application/json"}

def log_test(test_name, success, details=""):
    """Log test results"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} {test_name}")
    if details:
        print(f"   Details: {details}")
    print()

def test_health_endpoint():
    """Test 1: Health endpoint GET /api/"""
    print("=== Testing Health Endpoint ===")
    try:
        response = requests.get(f"{BASE_URL}/", headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "message" in data:
                log_test("Health endpoint", True, f"Status: {response.status_code}, Message: {data['message']}")
                return True
            else:
                log_test("Health endpoint", False, f"Missing 'message' field in response: {data}")
                return False
        else:
            log_test("Health endpoint", False, f"Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        log_test("Health endpoint", False, f"Exception: {str(e)}")
        return False

def test_mood_config_endpoints():
    """Test 2: Mood configuration endpoints"""
    print("=== Testing Mood Config Endpoints ===")
    results = []
    
    # Test GET /api/moods/defaults
    try:
        response = requests.get(f"{BASE_URL}/moods/defaults", headers=HEADERS, timeout=10)
        if response.status_code == 200:
            defaults = response.json()
            if isinstance(defaults, list) and len(defaults) > 0:
                # Check if each mood has required fields
                valid_moods = all('value' in mood and 'emoji' in mood and 'label' in mood for mood in defaults)
                if valid_moods:
                    log_test("GET /moods/defaults", True, f"Retrieved {len(defaults)} default moods")
                    results.append(True)
                else:
                    log_test("GET /moods/defaults", False, "Invalid mood structure in defaults")
                    results.append(False)
            else:
                log_test("GET /moods/defaults", False, f"Expected list of moods, got: {type(defaults)}")
                results.append(False)
        else:
            log_test("GET /moods/defaults", False, f"Status: {response.status_code}, Response: {response.text}")
            results.append(False)
    except Exception as e:
        log_test("GET /moods/defaults", False, f"Exception: {str(e)}")
        results.append(False)
    
    # Test GET /api/moods/config (should return defaults on first run)
    try:
        response = requests.get(f"{BASE_URL}/moods/config", headers=HEADERS, timeout=10)
        if response.status_code == 200:
            config = response.json()
            if "moods" in config and isinstance(config["moods"], list):
                log_test("GET /moods/config", True, f"Retrieved config with {len(config['moods'])} moods")
                results.append(True)
            else:
                log_test("GET /moods/config", False, f"Invalid config structure: {config}")
                results.append(False)
        else:
            log_test("GET /moods/config", False, f"Status: {response.status_code}, Response: {response.text}")
            results.append(False)
    except Exception as e:
        log_test("GET /moods/config", False, f"Exception: {str(e)}")
        results.append(False)
    
    # Test POST /api/moods/config with custom list
    custom_moods = [
        {"value": "excited", "emoji": "🤩", "label": "Excited", "color": "#ff6b6b"},
        {"value": "calm", "emoji": "😌", "label": "Calm", "color": "#4ecdc4"}
    ]
    
    try:
        payload = {"moods": custom_moods}
        response = requests.post(f"{BASE_URL}/moods/config", 
                               headers=HEADERS, 
                               json=payload, 
                               timeout=10)
        
        if response.status_code == 200:
            saved_config = response.json()
            if "moods" in saved_config and len(saved_config["moods"]) == 2:
                log_test("POST /moods/config", True, "Successfully saved custom mood config")
                results.append(True)
                
                # Verify the change persisted by getting config again
                verify_response = requests.get(f"{BASE_URL}/moods/config", headers=HEADERS, timeout=10)
                if verify_response.status_code == 200:
                    verify_config = verify_response.json()
                    if len(verify_config["moods"]) == 2:
                        log_test("POST /moods/config persistence", True, "Custom config persisted correctly")
                        results.append(True)
                    else:
                        log_test("POST /moods/config persistence", False, f"Config not persisted, got {len(verify_config['moods'])} moods")
                        results.append(False)
                else:
                    log_test("POST /moods/config persistence", False, f"Failed to verify persistence: {verify_response.status_code}")
                    results.append(False)
            else:
                log_test("POST /moods/config", False, f"Invalid response structure: {saved_config}")
                results.append(False)
        else:
            log_test("POST /moods/config", False, f"Status: {response.status_code}, Response: {response.text}")
            results.append(False)
    except Exception as e:
        log_test("POST /moods/config", False, f"Exception: {str(e)}")
        results.append(False)
    
    return all(results)

def test_entries_crud():
    """Test 3: Entries CRUD operations"""
    print("=== Testing Entries CRUD ===")
    results = []
    
    # Get today's date
    today = date.today().isoformat()
    
    # Test POST /api/entries (create)
    entry_data = {
        "date": today,
        "mood_value": "excited",
        "emoji": "🤩",
        "note": "Testing mood entry creation"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/entries", 
                               headers=HEADERS, 
                               json=entry_data, 
                               timeout=10)
        
        if response.status_code == 200:
            created_entry = response.json()
            if ("id" in created_entry and 
                created_entry["date"] == today and 
                created_entry["mood_value"] == "excited"):
                
                entry_id = created_entry["id"]
                log_test("POST /entries (create)", True, f"Created entry with ID: {entry_id}")
                results.append(True)
                
                # Test POST /api/entries (update same date)
                updated_data = {
                    "date": today,
                    "mood_value": "calm",
                    "emoji": "😌", 
                    "note": "Updated mood entry for same date"
                }
                
                update_response = requests.post(f"{BASE_URL}/entries",
                                              headers=HEADERS,
                                              json=updated_data,
                                              timeout=10)
                
                if update_response.status_code == 200:
                    updated_entry = update_response.json()
                    if (updated_entry["id"] == entry_id and 
                        updated_entry["mood_value"] == "calm" and
                        updated_entry["note"] == "Updated mood entry for same date"):
                        log_test("POST /entries (update)", True, "Successfully updated existing entry")
                        results.append(True)
                    else:
                        log_test("POST /entries (update)", False, f"Update failed or incorrect data: {updated_entry}")
                        results.append(False)
                else:
                    log_test("POST /entries (update)", False, f"Update failed: {update_response.status_code}")
                    results.append(False)
                
                # Test GET /api/entries with date range
                start_date = today
                end_date = today
                
                get_response = requests.get(f"{BASE_URL}/entries?start={start_date}&end={end_date}",
                                          headers=HEADERS,
                                          timeout=10)
                
                if get_response.status_code == 200:
                    entries = get_response.json()
                    if isinstance(entries, list) and len(entries) == 1:
                        entry = entries[0]
                        if (entry["id"] == entry_id and 
                            entry["mood_value"] == "calm"):
                            log_test("GET /entries with range", True, f"Retrieved 1 entry for date range")
                            results.append(True)
                        else:
                            log_test("GET /entries with range", False, f"Entry data mismatch: {entry}")
                            results.append(False)
                    else:
                        log_test("GET /entries with range", False, f"Expected 1 entry, got {len(entries) if isinstance(entries, list) else 'non-list'}")
                        results.append(False)
                else:
                    log_test("GET /entries with range", False, f"Status: {get_response.status_code}")
                    results.append(False)
                
                # Test DELETE /api/entries/{id}
                delete_response = requests.delete(f"{BASE_URL}/entries/{entry_id}",
                                                headers=HEADERS,
                                                timeout=10)
                
                if delete_response.status_code == 200:
                    delete_result = delete_response.json()
                    if delete_result.get("ok"):
                        log_test("DELETE /entries/{id}", True, f"Successfully deleted entry {entry_id}")
                        results.append(True)
                        
                        # Verify deletion by getting entries again
                        verify_response = requests.get(f"{BASE_URL}/entries?start={start_date}&end={end_date}",
                                                     headers=HEADERS,
                                                     timeout=10)
                        
                        if verify_response.status_code == 200:
                            remaining_entries = verify_response.json()
                            if isinstance(remaining_entries, list) and len(remaining_entries) == 0:
                                log_test("DELETE verification", True, "Entry successfully removed from database")
                                results.append(True)
                            else:
                                log_test("DELETE verification", False, f"Entry still exists: {len(remaining_entries)} entries found")
                                results.append(False)
                        else:
                            log_test("DELETE verification", False, f"Failed to verify deletion: {verify_response.status_code}")
                            results.append(False)
                    else:
                        log_test("DELETE /entries/{id}", False, f"Delete response invalid: {delete_result}")
                        results.append(False)
                else:
                    log_test("DELETE /entries/{id}", False, f"Status: {delete_response.status_code}")
                    results.append(False)
                    
            else:
                log_test("POST /entries (create)", False, f"Invalid entry structure: {created_entry}")
                results.append(False)
        else:
            log_test("POST /entries (create)", False, f"Status: {response.status_code}, Response: {response.text}")
            results.append(False)
            
    except Exception as e:
        log_test("POST /entries (create)", False, f"Exception: {str(e)}")
        results.append(False)
    
    return all(results)

def test_pdf_export():
    """Test 4: PDF export functionality"""
    print("=== Testing PDF Export ===")
    
    # First create some test entries for the last 3 days
    test_entries = []
    for i in range(3):
        test_date = (date.today() - timedelta(days=i)).isoformat()
        entry_data = {
            "date": test_date,
            "mood_value": ["excited", "calm", "happy"][i],
            "emoji": ["🤩", "😌", "😀"][i],
            "note": f"Test entry for {test_date}"
        }
        
        try:
            response = requests.post(f"{BASE_URL}/entries", 
                                   headers=HEADERS, 
                                   json=entry_data, 
                                   timeout=10)
            if response.status_code == 200:
                test_entries.append(response.json())
        except Exception as e:
            print(f"Failed to create test entry for {test_date}: {e}")
    
    if len(test_entries) == 0:
        log_test("PDF Export setup", False, "Could not create test entries for PDF export")
        return False
    
    # Test PDF export
    start_date = (date.today() - timedelta(days=2)).isoformat()
    end_date = date.today().isoformat()
    
    try:
        response = requests.get(f"{BASE_URL}/export/pdf?start={start_date}&end={end_date}",
                              headers=HEADERS,
                              timeout=30)
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            content_length = len(response.content)
            
            if content_type == 'application/pdf' and content_length > 0:
                log_test("GET /export/pdf", True, f"PDF generated successfully, size: {content_length} bytes")
                
                # Clean up test entries
                for entry in test_entries:
                    try:
                        requests.delete(f"{BASE_URL}/entries/{entry['id']}", headers=HEADERS, timeout=10)
                    except:
                        pass
                
                return True
            else:
                log_test("GET /export/pdf", False, f"Invalid content type or empty: {content_type}, size: {content_length}")
                return False
        else:
            log_test("GET /export/pdf", False, f"Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        log_test("GET /export/pdf", False, f"Exception: {str(e)}")
        return False

def main():
    """Run all backend tests"""
    print("🧪 Starting Backend API Tests")
    print(f"Base URL: {BASE_URL}")
    print("=" * 50)
    
    test_results = []
    
    # Run tests in priority order (high first)
    test_results.append(test_mood_config_endpoints())
    test_results.append(test_entries_crud())
    test_results.append(test_pdf_export())
    test_results.append(test_health_endpoint())  # Low priority last
    
    print("=" * 50)
    print("🏁 Test Summary")
    print(f"Total tests: 4")
    print(f"Passed: {sum(test_results)}")
    print(f"Failed: {4 - sum(test_results)}")
    
    if all(test_results):
        print("✅ All backend tests PASSED!")
        return 0
    else:
        print("❌ Some backend tests FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())