#from curl_cffi import requests
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import time
import os
import math

class ShowDetails(BaseModel):
	id: Optional[int] = None
	title: Optional[str] = None
	releaseDate: Optional[str] = None
	rating: Optional[str] = None
	genres: Optional[list] = None
	description: Optional[str] = None
	duration: Optional[int] = None
	tagline: Optional[str] = None
	production: Optional[dict] = None

class reviewDetails(BaseModel):
	quote: Optional[str] = None
	score: Optional[int] = None
	date: Optional[str] = None
	author: Optional[str] = None
	publicationName: Optional[str] = None

def start_session(url):
	headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"}	
	session = requests.Session()
	retry = Retry(connect=10, backoff_factor=0.5)
	adapter = HTTPAdapter(max_retries=retry)
	session.mount('http://', adapter)
	session.mount('https://', adapter)

	response = session.get(url, headers=headers)
	return response

if not os.path.exists("data"):
	os.makedirs("data")

show_list = []
reviews_list = []

product_type_upper = "tv"
product_type_lower = "shows"

review_types = ["user", "critic"]
offset = 0
offset_limit = 10000
show_limit = 25
review_limits = [500, 100]

upper_url = f"https://backend.metacritic.com/finder/metacritic/web?sortBy=-metaScore&productType={product_type_upper}&page=2&releaseYearMin=1910&releaseYearMax=2025&offset={offset}&limit={show_limit}&apiKey=1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"
upper_response = start_session(upper_url)

show_len = upper_response.json()["data"]["totalResults"]

for i in range(math.ceil(show_len/show_limit)):
	
	upper_url = f"https://backend.metacritic.com/finder/metacritic/web?sortBy=-metaScore&productType={product_type_upper}&page=2&releaseYearMin=1910&releaseYearMax=2025&offset={offset}&limit={show_limit}&apiKey=1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"
	upper_response = start_session(upper_url)
	
	while upper_response.status_code != 200:
		
		print("ERROR at offset -->", offset, "Trying Again !")
		time.sleep(1)           
		upper_response = start_session(upper_url)

	offset += show_limit
	for resp in upper_response.json()["data"]["items"]:
		
		num_seasons = resp["numberOfSeasons"]
		show_slug = resp["slug"]

		try:
			show_url = f"https://backend.metacritic.com/composer/metacritic/pages/{product_type_lower}/{show_slug}/web?filter=all&sort=date&apiKey=1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"
			show_response = start_session(show_url)
			
			while show_response.status_code != 200:
				
				print("ERROR at show details -->", show_slug, "Trying Again !")
				time.sleep(1)
				show_response = start_session(show_url)
				
			show_details = show_response.json()            
			show_list.append(dict(ShowDetails(**show_details["components"][0]["data"]["item"])))
			
			if product_type_lower == 'shows':
				show_list[-1]["num_seasons"] = num_seasons
			
			show_list[-1]["metascore"] = show_details["components"][4]["data"]["item"]["score"]
			show_list[-1]["metascore_count"] = show_details["components"][4]["data"]["item"]["reviewCount"]
			show_list[-1]["metascore_sentiment"] = show_details["components"][4]["data"]["item"]["sentiment"]
			
			show_list[-1]["userscore"] = show_details["components"][6]["data"]["item"]["score"]
			show_list[-1]["userscore_count"] = show_details["components"][6]["data"]["item"]["reviewCount"]
			show_list[-1]["userscore_sentiment"] = show_details["components"][6]["data"]["item"]["sentiment"]
			
			if "genres" in show_list[-1].keys() and show_list[-1]["genres"] is not None:
				show_list[-1]["genres"] = ",".join([genre["name"] for genre in show_list[-1]["genres"] if genre["name"] is not None])
			else:
				show_list[-1]["genres"] = None

			show_list[-1]["production_companies"] = ",".join([prod_comp["name"] for prod_comp in show_list[-1]["production"]["companies"] if prod_comp["name"] is not None])
			
			if product_type_lower == 'shows':
				show_list[-1]["created_by"] = ",".join([prod_comp["entertainmentProduct"]["name"] for prod_comp in show_list[-1]["production"]["crew"] if "created by" in prod_comp["roles"] and prod_comp["name"] is not None])

			show_list[-1]["director"] = ",".join([prod_comp["entertainmentProduct"]["name"] for prod_comp in show_list[-1]["production"]["crew"] if "Director" in prod_comp["entertainmentProduct"]["profession"] and prod_comp["entertainmentProduct"]["name"] is not None])
			show_list[-1]["writer"] = ",".join([prod_comp["entertainmentProduct"]["name"] for prod_comp in show_list[-1]["production"]["crew"] if "Writer" in prod_comp["entertainmentProduct"]["profession"] and prod_comp["entertainmentProduct"]["name"] is not None])
			show_list[-1]["top_cast"] = ",".join([prod_comp["name"] for prod_comp in show_list[-1]["production"]["cast"] if prod_comp["name"] is not None])
			
			show_list[-1].pop("production")
			
			for review_type, review_limit in zip(review_types, review_limits):

				review_offset = 0
				review_url = f"https://backend.metacritic.com/reviews/metacritic/{review_type}/{product_type_lower}/{show_slug}/web?apiKey=1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u&offset={review_offset}&limit={review_limit}&filterBySentiment=all&sort=score&componentName={review_type}-reviews&componentDisplayName={review_type}+Reviews&componentType=ReviewList"
				review_response = start_session(review_url)
				
				while review_response.status_code != 200:
					
					print("ERROR at show reviews -->", show_slug, "|", review_type, "- Trying again !")
					time.sleep(1)
					review_response = start_session(review_url)
					
				review_details = review_response.json()
				review_number = review_details["data"]["totalResults"]
				
				if review_number > 0:
					
					for reviews in review_details["data"]["items"]:
						reviews_list.append(dict(reviewDetails(**reviews)))
						reviews_list[-1]["review_type"] = review_type
						reviews_list[-1]["show_name"] = resp["title"]
						reviews_list[-1]["show_id"] = resp["id"]
						
					if review_number > review_limit:
						while review_offset < review_number:
							review_offset += review_limit

							review_url = f"https://backend.metacritic.com/reviews/metacritic/{review_type}/{product_type_lower}/{show_slug}/web?apiKey=1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u&offset={review_offset}&limit={review_limit}&filterBySentiment=all&sort=score&componentName={review_type}-reviews&componentDisplayName={review_type}+Reviews&componentType=ReviewList"
							review_response = start_session(review_url)
							
							while review_response.status_code != 200:
								
								print("ERROR at show reviews -->", show_slug, "|", review_type, "| offset of", review_offset, "Trying again !")
								time.sleep(1)
								review_response = start_session(review_url)
							
							review_details = review_response.json()
							for reviews in review_details["data"]["items"]:
								reviews_list.append(dict(reviewDetails(**reviews)))
								reviews_list[-1]["review_type"] = review_type
								reviews_list[-1]["show_name"] = resp["title"]
								reviews_list[-1]["show_id"] = resp["id"]
				else:
					continue

		except Exception as e:
			print(e, "-->", show_slug, "- at offset -", i)
			continue

show_df = pd.DataFrame(show_list)
if "production" in show_df.columns:
    show_df.drop(columns=["production"], inplace=True)

show_df.drop(show_df[show_df["id"].duplicated()].index, axis=0, inplace=True)

#Multiply user scores by 10 to make them compatible with critic score
show_df["userscore"] = show_df["userscore"].apply(lambda x: x*10 if x is not None else x)

show_df.to_csv("data/tv_shows.csv", index=False)

reviews_df = pd.DataFrame(reviews_list)
reviews_df = reviews_df[["show_id", "show_name", "quote", "score", "date", "author", "publicationName", "review_type"]]

#Multiply user scores by 10 to make them compatible with critic scores
def convertUserScores(col1, col2):
	if col2 == 'user':
		return col1*10
	else:
		return col1

reviews_df["score"] = reviews_df[["score", "review_type"]].apply(lambda x: convertUserScores(*x), axis=1)

reviews_df.drop_duplicates().to_csv("data/tv_shows_reviews.csv", index=False)