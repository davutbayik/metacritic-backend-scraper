import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import time
import os
import math
from datetime import datetime

# Define a model to store game details
class gameDetails(BaseModel):
	id: Optional[int] = None
	title: Optional[str] = None
	releaseDate: Optional[str] = None
	rating: Optional[str] = None
	genres: Optional[list] = None
	description: Optional[str] = None
	platforms: Optional[list] = None
	production: Optional[dict] = None

# Define a model to store review details
class reviewDetails(BaseModel):
	quote: Optional[str] = None
	score: Optional[int] = None
	date: Optional[str] = None
	platform: Optional[str] = None
	author: Optional[str] = None
	publicationName: Optional[str] = None

# Function to start a session with retry logic for making HTTP requests
def start_session(url):
	headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"}	
	session = requests.Session()
	retry = Retry(connect=10, backoff_factor=0.5)
	adapter = HTTPAdapter(max_retries=retry)
	session.mount('http://', adapter)
	session.mount('https://', adapter)

	response = session.get(url, headers=headers)
	return response

# Create a directory to store data if it doesn't exist
if not os.path.exists("data"):
	os.makedirs("data")

# Initialize lists to store game and review data
games_list, review_list = [], []

# Define scraping parameters
product_type = "games"
review_types = ["user", "critic"]
offset = 0
offset_limit = 10000
games_limit = 25
review_limits = [500, 100]
current_year = datetime.now().year

# Get the total number of games available
upper_url = f"https://backend.metacritic.com/finder/metacritic/web?sortBy=-metaScore&productType={product_type}&page=2&releaseYearMin=1900&releaseYearMax={current_year}&offset={offset}&limit={games_limit}&apiKey=1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"
upper_response = start_session(upper_url)

games_len = upper_response.json()["data"]["totalResults"]

# Loop through all available games
for i in range(math.ceil(games_len/games_limit)):
    
	upper_url = f"https://backend.metacritic.com/finder/metacritic/web?sortBy=-metaScore&productType={product_type}&page=2&releaseYearMin=1900&releaseYearMax={current_year}&offset={offset}&limit={games_limit}&apiKey=1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"
	upper_response = start_session(upper_url)
    
    # Retry request if response is not successful
	while upper_response.status_code != 200:
		
		print("ERROR at offset -->", offset, "Trying Again !")
		time.sleep(1)           
		upper_response = start_session(upper_url)

	offset += games_limit

	# Extract game details
	for resp in upper_response.json()["data"]["items"]:
		
		slug_name = resp["slug"]

		try:
			# Fetch detailed information for each game
			game_url = f"https://backend.metacritic.com/composer/metacritic/pages/{product_type}/{slug_name}/web?filter=all&sort=date&apiKey=1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"
			game_response = start_session(game_url)
			
			while game_response.status_code != 200:
				
				print("ERROR at game details -->", slug_name, "Trying Again !")
				time.sleep(1)
				game_response = start_session(game_url)
				
			game_details = game_response.json()
			games_list.append(dict(gameDetails(**game_details["components"][0]["data"]["item"])))

			# Extract metascore details
			games_list[-1]["metascore"] = game_details["components"][6]["data"]["item"]["score"]
			games_list[-1]["metascore_count"] = game_details["components"][6]["data"]["item"]["reviewCount"]
			games_list[-1]["metascore_sentiment"] = game_details["components"][6]["data"]["item"]["sentiment"]
			
			# Extract user score details
			games_list[-1]["userscore"] = game_details["components"][8]["data"]["item"]["score"]
			games_list[-1]["userscore_count"] = game_details["components"][8]["data"]["item"]["reviewCount"]
			games_list[-1]["userscore_sentiment"] = game_details["components"][8]["data"]["item"]["sentiment"]
			
			if "genres" in games_list[-1].keys() and games_list[-1]["genres"] is not None:
				games_list[-1]["genres"] = ",".join([genre["name"] for genre in games_list[-1]["genres"] if genre["name"] is not None])
			else:
				games_list[-1]["genres"] = None

			# Extract platform and developer details
			games_list[-1]["platforms"] = ",".join([platform["name"] for platform in game_details["components"][0]["data"]["item"]["platforms"] if platform["criticScoreSummary"]["score"] is not None])
			games_list[-1]["platform_metascores"] = ",".join([str(platform["criticScoreSummary"]["score"]) for platform in game_details["components"][0]["data"]["item"]["platforms"] if platform["criticScoreSummary"]["score"] is not None])
			games_list[-1]["developer"] = ",".join([prod_comp["name"] for prod_comp in games_list[-1]["production"]["companies"] if "Developer" in prod_comp["typeName"] and prod_comp["name"] is not None])
			games_list[-1]["publisher"] = ",".join([prod_comp["name"] for prod_comp in games_list[-1]["production"]["companies"] if "Publisher" in prod_comp["typeName"] and prod_comp["name"] is not None])
			
			platform_slugs = [platform["slug"] for platform in game_details["components"][0]["data"]["item"]["platforms"] if platform["slug"] is not None]
	
			games_list[-1].pop("production")

			# Fetch reviews for each game across platforms
			for review_type, review_limit in zip(review_types, review_limits):
				for platform_slug in platform_slugs:

					review_offset = 0
					review_url = f"https://backend.metacritic.com/reviews/metacritic/{review_type}/{product_type}/{slug_name}/platform/{platform_slug}/web?apiKey=1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u&offset={review_offset}&limit={review_limit}&filterBySentiment=all&sort=score&componentName={review_type}-reviews&componentDisplayName={review_type}+Reviews&componentType=ReviewList"
					review_response = start_session(review_url)
					
					while review_response.status_code != 200 and review_response.status_code != 404:

						print("ERROR at game reviews -->", slug_name, "|", review_type, "|", platform_slug, "- Trying again !")
						time.sleep(1)
						review_response = start_session(review_url)
					
					# Process reviews
					review_details = review_response.json()
					review_number = review_details["data"]["totalResults"]
					
					if review_number > 0:
						
						for reviews in review_details["data"]["items"]:
							review_list.append(dict(reviewDetails(**reviews)))
							review_list[-1]["review_type"] = review_type
							review_list[-1]["game_name"] = resp["title"]
							review_list[-1]["game_id"] = resp["id"]
							
						if review_number > review_limit:
							while review_offset < review_number and review_offset < offset_limit:
								review_offset += review_limit

								if review_offset < offset_limit:
									review_url = f"https://backend.metacritic.com/reviews/metacritic/{review_type}/{product_type}/{slug_name}/platform/{platform_slug}/web?apiKey=1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u&offset={review_offset}&limit={review_limit}&filterBySentiment=all&sort=score&componentName={review_type}-reviews&componentDisplayName={review_type}+Reviews&componentType=ReviewList"
									review_response = start_session(review_url)

									while review_response.status_code != 200 and review_response.status_code != 404:
										
										print("ERROR at game reviews -->", slug_name, "|", review_type, "| offset of", review_offset, "Trying again !")
										time.sleep(1)
										review_response = start_session(review_url)
									
									review_details = review_response.json()
									for reviews in review_details["data"]["items"]:
										review_list.append(dict(reviewDetails(**reviews)))
										review_list[-1]["review_type"] = review_type
										review_list[-1]["game_name"] = resp["title"]
										review_list[-1]["game_id"] = resp["id"]
					else:
						continue

		except Exception as e:
			print(e, "-->", slug_name, "- at offset -", i)
			continue

games_df = pd.DataFrame(games_list)
if "production" in games_df.columns:
    games_df.drop(columns=["production"], inplace=True)

games_df.drop(games_df[games_df["id"].duplicated()].index, axis=0, inplace=True)

#Multiply user scores by 10 to make them compatible with critic score
games_df["userscore"] = games_df["userscore"].apply(lambda x: x*10 if x is not None else x)

# Save game data to CSV
games_df.to_csv("data/games.csv", index=False)

reviews_df = pd.DataFrame(review_list)
reviews_df = reviews_df[["game_id", "game_name", "quote", "score", "date", "platform", "author", "publicationName", "review_type"]]

#Multiply user scores by 10 to make them compatible with critic scores
def convertUserScores(col1, col2):
	if col2 == 'user':
		return col1*10
	else:
		return col1

reviews_df["score"] = reviews_df[["score", "review_type"]].apply(lambda x: convertUserScores(*x), axis=1)

# Save review data to CSV
reviews_df.drop_duplicates().to_csv("data/games_reviews.csv", index=False)
