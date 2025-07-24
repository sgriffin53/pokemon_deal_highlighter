import sys
import mysql.connector
import json
from flask import Flask, request, redirect, url_for, jsonify
from flask_cors import CORS
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import re

class Value:
    def __init__(self):
        self.name = ""
        self.set = None
        self.ungraded = None
        self.psa9 = None
        self.psa10 = None
        self.card_id = None

def get_values_from_db():
    with open('sql_login.json', 'r') as config_file:
        config = json.load(config_file)

    connection = mysql.connector.connect(
        host=config['host'],
        user=config['user'],
        password=config['password'],
        database=config['database'],
        auth_plugin=config['auth_plugin']  # Specify the authentication plugin
    )

    cursor = connection.cursor()

    # Define the query
    query = "SELECT * FROM card_values"

    # Execute the query with parameters
    cursor.execute(query)

    # Fetch all results
    results = cursor.fetchall()
    values_dict = {}
    for row in results:
        card_id = row[6]
        if card_id is None: continue
        set_name = row[2]
        if set_name.lower() not in values_dict:
            values_dict[set_name.lower()] = {}
        if card_id not in values_dict[set_name.lower()]:
            values_dict[set_name.lower()][card_id] = []
        value = Value()
        value.name = row[1]
        value.set = row[2]
        value.card_id = card_id
        value.ungraded = row[3]
        value.psa9 = row[4]
        value.psa10 = row[5]
        values_dict[set_name.lower()][card_id].append(value)
    connection.close()
    return values_dict

def get_card_id(title):
    if 'booster pack' in title.lower():
        if '#' in title or '/' in title: return None
        return 'booster pack'
    if 'booster box' in title.lower():
        if '#' in title or '/' in title: return None
        return 'booster box'
    if 'elite trainer box' in title.lower():
        if '#' in title or '/' in title: return None
        return 'elite trainer box'
    for word in title.split(" "):
        if '/' in word or '#' in word:
            word = word.replace('#','')
            if '/' in word:
                word = word.split("/")[0]
         #   if not word.isdigit():
         #       continue
            word = word.lstrip('00')
            word = word.lstrip('0')
            return word
    return None

def is_card_match(title, card_name, id_matches):
    title = title.replace("’", "'")
    # matches title to stored card name
    bracket_text = ''
    if "[" in card_name and "]":
        bracket_text = card_name.split("[")[1].split("]")[0]
    if bracket_text == 'Holo':
        if 'non holo' in title.lower() or 'non-holo' in title.lower():
            return False
    pokemon_text = card_name
    if "[" in card_name:
        pokemon_text = card_name.split("[")[0]
    if "#" in pokemon_text:
        pokemon_text = pokemon_text.split("#")[0]
    pokemon_text = pokemon_text.strip()
    if pokemon_text.lower() in title.lower():
        if bracket_text.lower() in title.lower(): return True
        #else:
            #if id_matches == 1: return True
    return False

def get_card_value(item_title, this_set, card_id):
    if this_set not in values_dict:
        return None
    if card_id not in values_dict[this_set]:
        return None
    value_info = values_dict[this_set][card_id]
    if len(value_info) == 1:
        value_info = value_info[0]
        is_match = is_card_match(item_title, value_info.name, 1)
        if not is_match: return None
    else:
        matches = []
        for info in value_info:
            if "[1st edition]" in info.name.lower(): continue
            if "[play]" in info.name.lower(): continue
            if "[error]" in info.name.lower(): continue
            if "[1999-2000]" in info.name.lower(): continue
            if "[shadowless]" in info.name.lower(): continue
            is_match = is_card_match(item_title.replace("1st edition", "").replace("1st Edition", ""), info.name,
                                     len(value_info))
            if is_match:
                matches.append(info)
        if len(matches) > 1:
            biggest_name = 0
            winner = None
            for match in matches:
                if len(match.name) > biggest_name:
                    winner = match
                    biggest_name = len(match.name)
            value_info = winner
        else:
            if len(matches) == 1:
                value_info = matches[0]
            else:
                return None
    return value_info


def append_affiliate_params(url):
    aff_params = [
        ('campid', '5339084796'),
        ('toolid', '10001'),
        ('mkevt', '1'),
        ('customid', 'extension')
    ]

    parsed = urlparse(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)

    # Remove existing aff params if present (prevent duplicates)
    query = [(k, v) for (k, v) in query if k not in dict(aff_params)]

    # Prepend affiliate params
    final_query = aff_params + query
    final_url = urlunparse(parsed._replace(query=urlencode(final_query)))

    return final_url

app = Flask(__name__)
CORS(app)  # ← Allow all origins for now
values_dict = get_values_from_db()

GBP_USD = 1.31
@app.route("/get_values", methods=["POST"])
def root():
    global values_dict
    data = request.get_json()

    if not data or 'listings' not in data:
        return jsonify({"error": "Missing listings"}), 400

    listings = data['listings']
    return_listings = []

    for listing in listings:
        item_title = listing['title']
        item_title = item_title.replace("Champions Path", "Champion's Path") # fix common listing typo
        item_title = item_title.replace(" 2/", " - 2/") # prevents base set blastoise being counted as base set 2
        item_price = listing['price']
        item_url = listing['url']

        item_title = item_title.replace("’", "'")

        if "to" in item_price: continue
        full_set_names = values_dict.keys()

        sorted_sets = sorted(full_set_names, key=lambda s: len(s), reverse=True)

        matched_set = next(
            (s for s in sorted_sets if re.search(rf'\b{re.escape(s.lower())}\b', item_title.lower())),
            None
        )
        if not matched_set:
            continue

        this_set = matched_set
        card_id = get_card_id(item_title)
        if card_id not in values_dict.get(this_set, {}):
            continue

        value_info = get_card_value(item_title, this_set, card_id)
        if not value_info:
            value_info = get_card_value(item_title, 'promo', card_id)
            if not value_info:
                continue
        identified_as = value_info.name
        valuation = value_info.ungraded

        # Normalize price
        if isinstance(item_price, str):
            if '£' in item_price:
                item_price = float(item_price.replace("£", "").replace(",", "").strip()) * GBP_USD
            else:
                item_price = float(item_price.replace("$", "").replace(",", "").strip())

        # Calculate % over/under market
        delta = item_price - valuation
        percent = round((delta / valuation) * 100, 2) if valuation else 0

        if percent < 0:
            banner_text = f"{abs(percent)}% below market"
        elif percent > 0:
            banner_text = f"{percent}% above market"
        else:
            banner_text = "At market price"
        pc_link = 'pokemon-' + this_set.replace(" ", "-").lower() + "/" + identified_as.replace("#", "").replace("[",
                                                                                                                 "").replace(
            "]", "").replace(" ", "-").replace("'", "%27").lower()
        pc_link = 'https://pricecharting.com/game/' + pc_link
        modified_url = item_url
        ENABLE_AFFILIATE_LINKS = True
        if ENABLE_AFFILIATE_LINKS:
         #   if '?' in modified_url:
         #       modified_url += '&campid=5339084796&toolid=10001&mkevt=1&customid=extension'
         #   else:
         #       modified_url += '?campid=5339084796&toolid=10001&mkevt=1&customid=extension'
            modified_url = append_affiliate_params(item_url)
        print(modified_url)
        return_listings.append({
            'identified_set': this_set.title().replace("'S", "'s"),
            'identified_card': identified_as,
            'price': round(item_price, 2),
            'url': item_url,
            'modified_url': modified_url,  # optional
            'pricecharting_url': pc_link,
            'valuation': round(valuation, 2),
            'banner_text': banner_text,
            'percent': percent
        })

    # ✅ Return listings as JSON array
    return jsonify(return_listings)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)