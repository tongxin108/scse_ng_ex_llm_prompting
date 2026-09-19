## Import the necessary modules
import json
from ollama import chat
## Import the function from the module parse_data
from parse_data import load_items, get_unclaimed_items, save_result

## Build your prompt based on the description the user provides 
## and the items that are available in the lost-and-found database.
## The model must follow the rules listed in the README file
## The function should return the system prompt and the user prompt.
## You may need to use json.dumps() to convert the available_items list into a JSON string.

def build_prompt(description, available_items):
    
    system_prompt = """You are a campus lost-and-found matching assistant for a university.
    Your job is to compare a user's lost-item description against a database of 
    available (unclaimed) found items, and return possible matches.

    RULES YOU MUST FOLLOW:
    1. Use ONLY the items provided in the "Available items" list. Do NOT invent items.
    2. Not all details of an item must match to be a possible match.
    (e.g., if the user says "black bag", a "black backpack" is a possible match.)
    3. You MUST return ONLY a single valid JSON object.
    - Do NOT include any conversational filler.
    - Do NOT wrap the JSON in markdown code blocks (like ```json).
    - Do NOT add any text before or after the JSON.
    4. The JSON must follow EXACTLY this structure:

    {
        "matches": ["ITEM_ID_1", "ITEM_ID_2"],
        "confidence": "LOW"
    }

    5. "matches" contains all possible matching item IDs (as a list of strings).
    - If there is no match, return an empty list: []
    6. "confidence" MUST be exactly one of: "LOW", "MEDIUM", "HIGH".
    - HIGH: description matches many specific details (color + type + location).
    - MEDIUM: description matches some details (type + color OR type + location).
    - LOW: description matches only vague details, or matches are uncertain.
    7. If no items match at all, return:
    {"matches": [], "confidence": "LOW"}
    """
    items_json = json.dumps(available_items, indent=2, ensure_ascii=False)
    user_prompt = f"""Available items (JSON):{items_json}
    User's description of the lost item:"{description}"
    Now return ONLY the JSON object with the "matches" and "confidence" fields.
    """

    return system_prompt, user_prompt

    

## Logic to ask Qwen for all the possible matches based on the system prompt and user prompt.
## The function should return the response from Qwen.
def ask_qwen(system_prompt, user_prompt):
    response = chat(
        model="qwen3:8b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    )
    return response.message.content


## Logic to parse the response from Qwen and return the result. 
## You may need to use json.loads() to convert the response string into a suitable Python data structure.
def parse_response(response_text):
    text = response_text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if "```" in text:
        start = text.find("```")
        end = text.find("```", start + 3)
        if end != -1:
            block = text[start + 3:end]
            if block.lower().startswith("json"):
                block = block[4:]
            block = block.strip()
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"not vaild:\n{response_text}")
    


## Logic to validate the result returned by Qwen.
## It should check if the result is a dictionary, contains the keys "matches" and "confidence", and that the values are of the correct type.
## If everything is correct, then it should check if the item IDs in the "matches" list are valid IDs .
def validate_result(result, available_items):
    if not isinstance(result, dict):
        return False, f"result is not dict,got {type(result).__name__}"

    if "matches" not in result:
        return False, "missing 'matches' field"
    if "confidence" not in result:
        return False, "missing 'confidence' field"

    if not isinstance(result["matches"], list):
        return False, f"'matches' must be list,not {type(result['matches']).__name__}"
    for m in result["matches"]:
        if not isinstance(m, str):
            return False, f"'matches' elements must be strings, got {type(m).__name__}"

    if result["confidence"] not in ("LOW", "MEDIUM", "HIGH"):
        return False, f"'confidence' must be LOW/MEDIUM/HIGH, not '{result['confidence']}'"

    valid_ids = {item["id"] for item in available_items}
    for m in result["matches"]:
        if m not in valid_ids:
            return False, f"invalid item ID: '{m}', valid IDs are: {valid_ids}"

    return True, None


## Logic to display the matches found by Qwen in a user-friendly format.
## It should look something like this:
""" 
CAMPUS LOST-AND-FOUND ASSISTANT
==================================================

Describe the item you lost: I lost a black bag somewhere

Searching for possible matches...

MATCH RESULT
--------------------------------------------------
Confidence: MEDIUM

Possible matches:

ID: F101
Item: backpack
Color: black
Location: Library 2nd floor
Date found: 2026-09-15

Result saved to output/match_result.json
 """
## If no matches are found, it should display a message indicating that no matches were found, along with the empty list
def display_matches(result, available_items):
    print("\nMATCH RESULT")
    print("-" * 50)
    print(f"Confidence: {result['confidence']}")

    matches = result.get("matches", [])

    if not matches:
        print("\nNo matches found.")
        print("Possible matches: (empty list)")
        return

    item_map = {item["id"]: item for item in available_items}

    print("\nPossible matches:")
    for item_id in matches:
        item = item_map.get(item_id)
        if item is None:
            continue
        print(f"\nID: {item['id']}")
        print(f"Item: {item['item']}")
        print(f"Color: {item['color']}")
        print(f"Location: {item['location']}")
        print(f"Date found: {item['date']}")
    

## Control center for the entire program.
def main():
    print("CAMPUS LOST-AND-FOUND ASSISTANT")
    print("=" * 50)

    items = load_items("found_items.json")
    unclaimed_items = get_unclaimed_items(items)

    if not unclaimed_items:
        print("\n[INFO] There are no unclaimed items at the moment.")
        return

    description = input("\nDescribe the item you lost: ").strip()
    if not description:
        print("[ERROR] describe cannot be empty。")
        return

    print("\nSearching for possible matches...")


    system_prompt, user_prompt = build_prompt(description, unclaimed_items)

    try:
        raw_response = ask_qwen(system_prompt, user_prompt)
    except Exception as e:
        print(f"\n[ERROR] Failed to call the model: {e}")
        return

    try:
        result = parse_response(raw_response)
    except ValueError as e:
        print(f"\n[ERROR] Failed to parse model response: {e}")
        print(f"Original response:\n{raw_response}")
        return

    is_valid, err = validate_result(result, unclaimed_items)
    if not is_valid:
        print(f"\n[ERROR] result that model returned is not valid: {err}")
        print(f"orginal result: {result}")
        return

    display_matches(result, unclaimed_items)
    save_result(result, "match_result.json")


if __name__ == "__main__":
    main()