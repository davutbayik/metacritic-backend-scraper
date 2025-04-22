import time
import os
import re
import unicodedata
import logging
from typing import Optional, List, Dict
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pydantic import BaseModel
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

# Configure logging
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(levelname)s - %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S',
	handlers=[
		logging.StreamHandler(),
		logging.FileHandler("scraper_logs.log", mode='a')
	]
)

# Pydantic models
class GameDetails(BaseModel):
	id: Optional[int] = None
	title: Optional[str] = None
	releaseDate: Optional[str] = None
	rating: Optional[str] = None
	genres: Optional[list] = None
	description: Optional[str] = None
	platforms: Optional[list] = None
	production: Optional[dict] = None

class MovieShowDetails(BaseModel):
	id: Optional[int] = None
	title: Optional[str] = None
	releaseDate: Optional[str] = None
	seasonCount: Optional[int] = None
	rating: Optional[str] = None
	genres: Optional[list] = None
	description: Optional[str] = None
	duration: Optional[int] = None
	tagline: Optional[str] = None
	production: Optional[dict] = None

class GameReviewDetails(BaseModel):
	quote: Optional[str] = None
	platform: Optional[str] = None
	score: Optional[int] = None
	date: Optional[str] = None
	author: Optional[str] = None
	publicationName: Optional[str] = None

class MovieShowReviewDetails(BaseModel):
	quote: Optional[str] = None
	score: Optional[int] = None
	date: Optional[str] = None
	author: Optional[str] = None
	publicationName: Optional[str] = None

class MetacriticScraper:
	def __init__(self, product_type, product_limit=25, review_limits=[500, 100], offset_limit=10000):
		"""
		Initializes the MetacriticScraper with necessary settings and empty data containers.
		
		Args:
			product_type (str): Type of product to scrape ("games", "movies" or "shows)
			product_limit (int): Number of products to fetch per request
			review_limits (List[int]): Limits for [user, critic] reviews per request
			offset_limit (int): Maximum offset for pagination
		"""
		self.base_url = "https://backend.metacritic.com"
		self.api_key = "1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u" # Metacritic's public backend API
		self.product_type = product_type
		self.product_limit = product_limit
		self.review_limits = review_limits
		self.review_types = ["user", "critic"]
		self.offset_limit = offset_limit
		self.current_year = datetime.now().year
		self.product_list = []
		self.review_list = []

		os.makedirs("data", exist_ok=True)

	def build_session(self, url):
		"""
		Starts an HTTP session and performs a GET request to the given URL with automatic retries.

		Args:
			url (str): The URL to send the GET request to.

		Returns:
			requests.Response: The response object from the GET request.
		"""
		headers = {"User-Agent": "Mozilla/5.0"}
		session = requests.Session()
		retry = Retry(connect=10, backoff_factor=0.5)
		adapter = HTTPAdapter(max_retries=retry)
		session.mount('http://', adapter)
		session.mount('https://', adapter)
		
		return session.get(url, headers=headers)

	def send_request(self, url, allow_404=False):
		"""
		Sends a GET request with retry logic and custom headers to handle network issues.
		
		Args:
			url (str): The URL to request.
			allow_404 (bool): Whether to consider 404 responses as valid.
		
		Returns:
			requests.Response: The HTTP response object.
		"""
				
		response = self.build_session(url)
		while response.status_code != 200 and (not allow_404 or response.status_code != 404):
			logging.warning(f"Failed to fetch {self.product_type[:-1]} page with status code: {response.status_code}. Retrying")
			time.sleep(1)
			response = self.build_session(url)
			
		return response

	def slugify_media_name(self, name):
		"""
		Converts a title name to a URL-friendly slug format used in Metacritic URLs.
		
		Removes all non-alphanumeric characters except spaces,
		then replaces spaces with hyphens, resulting in clean, lowercase slugs.
		
		Examples:
			"The Legend of Zelda: Ocarina of Time" -> "the-legend-of-zelda-ocarina-of-time"
			"Avatar: The Way of Water" -> "avatar-the-way-of-water"
			"Breaking Bad" -> "breaking-bad"
			
		Args:
			name (str): The original game name.
		
		Returns:
			str: The slugified version of the game name.
		"""
		# Normalize to ASCII and lowercase
		name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('utf-8').lower()
		# Replace '+' with 'plus'
		name = name.replace('+', 'plus')
		# Remove all non-alphanumeric characters except spaces and hyphens
		name = re.sub(r'[^a-z0-9 \-]+', '', name)
		# Replace spaces with hyphens
		name = re.sub(r'\s+', '-', name)

		return name

	def build_review_url(self, slug, rtype, offset, limit):
		"""
		Constructs the URL to fetch reviews of a specific product.

		Args:
			slug (str): Slug of the product.
			rtype (str): Type of review ("user" or "critic").
			offset (int): Offset for pagination.
			limit (int): Number of reviews to fetch.

		Returns:
			str: A fully formatted URL for the Metacritic review endpoint.
		"""
		return f"{self.base_url}/reviews/metacritic/{rtype}/{self.product_type}/{slug}/web?apiKey={self.api_key}&offset={offset}&limit={limit}&filterBySentiment=all&sort=score&componentName={rtype}-reviews&componentDisplayName={rtype}+Reviews&componentType=ReviewList"

	def build_top_products_url(self, offset=0, limit=10, sort_by="-metaScore", year_min=1900, year_max=None):
		"""
		Constructs the URL to fetch top products based on criteria.

		Args:
			offset (int): Offset for pagination.
			limit (int): Number of products to fetch.
			sort_by (str): Sort criterion. (metaScore, userScore, releaseDate etc.)
			year_min (int): Minimum release year.
			year_max (Optional[int]): Maximum release year. Defaults to current year.

		Returns:
			str: The complete top product URL.
		"""
		if not year_max:
			year_max = self.current_year
		
		if self.product_type != "shows":
			return f"{self.base_url}/finder/metacritic/web?sortBy={sort_by}&productType={self.product_type}&page=1&releaseYearMin={year_min}&releaseYearMax={year_max}&offset={offset}&limit={limit}&apiKey={self.api_key}"
		else:
			return f"{self.base_url}/finder/metacritic/web?sortBy={sort_by}&productType=tv&page=1&releaseYearMin={year_min}&releaseYearMax={year_max}&offset={offset}&limit={limit}&apiKey={self.api_key}"
	
	def fetch_product(self, product_name, single_title=True):
		"""
		Fetches product details and associated reviews by slug name.

		Args:
			slug_name (str): The slug name of the product.

		Returns:
			Tuple[dict, list]: Product metadata and a list of reviews.
		"""
		try:
			slug_name = self.slugify_media_name(product_name)
			product_url = f"{self.base_url}/composer/metacritic/pages/{self.product_type}/{slug_name}/web?filter=all&sort=date&apiKey={self.api_key}"
			product_response = self.send_request(product_url)
			
			if single_title:
				logging.info(f"Fetching {self.product_type[:-1]}: {product_name}")
			
			title_details = product_response.json()

			if self.product_type == "movies" or self.product_type == "shows":
				product_data = dict(MovieShowDetails(**title_details["components"][0]["data"]["item"]))
				detail_index = 4
	
			elif self.product_type == "games":
				product_data = dict(GameDetails(**title_details["components"][0]["data"]["item"]))
				detail_index = 6                
			
			# Extract score details
			product_data["metascore"] = title_details["components"][detail_index]["data"]["item"].get("score")
			product_data["metascore_count"] = title_details["components"][detail_index]["data"]["item"].get("reviewCount")
			product_data["metascore_sentiment"] = title_details["components"][detail_index]["data"]["item"].get("sentiment")
			
			product_data["userscore"] = title_details["components"][detail_index+2]["data"]["item"].get("score")
			product_data["userscore"] = product_data["userscore"]*10 if product_data["userscore"] is not None else product_data["userscore"]
			product_data["userscore_count"] = title_details["components"][detail_index+2]["data"]["item"].get("reviewCount")
			product_data["userscore_sentiment"] = title_details["components"][detail_index+2]["data"]["item"].get("sentiment")

			# Format genres
			if "genres" in product_data:
				product_data["genres"] = ",".join([g["name"] for g in product_data["genres"] if g.get("name")])
			else:
				product_data["genres"] = None
			
			# Extract production/platform details
			if self.product_type == "movies" or self.product_type == "shows":
				production = product_data.get("production", {})

				if self.product_type == 'shows':
					product_data["created_by"] = ",".join([prod_comp["entertainmentProduct"]["name"] 
						for prod_comp in product_data["production"]["crew"] if "created by" in prod_comp["roles"] and prod_comp["name"] is not None])
				
				if production:
					product_data["production_companies"] = ",".join([p["name"] for p in production.get("companies", []) if p.get("name")])
					product_data["director"] = ",".join([c["entertainmentProduct"]["name"] for c in production.get("crew", []) if "Director" in c["entertainmentProduct"].get("profession", [])])
					product_data["writer"] = ",".join([c["entertainmentProduct"]["name"] for c in production.get("crew", []) if "Writer" in c["entertainmentProduct"].get("profession", [])])
					product_data["top_cast"] = ",".join([c["name"] for c in production.get("cast", []) if c.get("name")])

			elif self.product_type == "games":
				platforms_data = title_details["components"][0]["data"]["item"]["platforms"]
								
				product_data["platforms"] = ",".join([p["name"] for p in platforms_data
						if p.get("criticScoreSummary", {}).get("score") is not None and p.get("name")
					])
				
				product_data["platform_metascores"] = ",".join([str(p["criticScoreSummary"]["score"]) for p in platforms_data
						if p.get("criticScoreSummary", {}).get("score") is not None
					])
			
				if not product_data.get("production", {}).get("companies"):
					product_data["developer"] = None
					product_data["publisher"] = None
				
				companies = product_data["production"]["companies"]
				
				product_data["developer"] = ",".join([
					pc["name"] for pc in companies
					if "Developer" in pc.get("typeName", "") and pc.get("name")
				])
				
				product_data["publisher"] = ",".join([
					pc["name"] for pc in companies
					if "Publisher" in pc.get("typeName", "") and pc.get("name")
				])
			
			product_data.pop("production", None)            
			reviews = self._fetch_product_reviews(slug_name, product_data["title"], product_data["id"])
			
			if single_title:
				self.product_list.append(product_data)
				self.review_list.extend(reviews)        
				self._save_data()
		
			return product_data, reviews
		
		except Exception as e:
			logging.error(f"Error fetching {self.product_type[:-1]} {product_name}: {e}")
			return None, None

	def _fetch_product_reviews(self, slug_name, product_title, product_id):
		"""
		Internal method to fetch all user and critic reviews for a product.

		Args:
			slug_name (str): Slug of the product.
			product_title (str): Title of the product.
			product_id (int): ID of the product.

		Returns:
			list: A list of formatted review dictionaries.
		"""
		reviews = []
		for review_type, review_limit in zip(self.review_types, self.review_limits):
			offset = 0

			while offset < self.offset_limit:
				review_url = self.build_review_url(slug_name, review_type, offset, review_limit)
				response = self.send_request(review_url)
	
				try:
					review_data = response.json()["data"]
					for r in review_data["items"]:
						
						if self.product_type == "movies" or self.product_type == "shows":
							review = dict(MovieShowReviewDetails(**r))
						elif self.product_type == "games":
							review = dict(GameReviewDetails(**r))
					
						review.update({"review_type": review_type, "product_title": product_title, "product_id": product_id})
						if review["review_type"] == "user":
							review["score"] = review["score"] * 10

						reviews.append(review)
						
					if len(review_data["items"]) < review_limit:
						break
					
					offset += review_limit
				except Exception as e:
					logging.error(f"Error parsing {review_type} reviews for {product_title}: {e}")
					break
	
		return reviews

	def fetch_all_products(self):
		"""
		Fetches all available product on Metacritic along with their reviews.

		Returns:
			Tuple[List[dict], List[dict]]: Lists of product and review data.
		"""
		self.product_list = []
		self.review_list = []
		
		logging.info(f"Fetching all {self.product_type} from Metacritic")
		
		url = self.build_top_products_url(limit=1)
		response = self.send_request(url)
		total = response.json()["data"]["totalResults"]
		logging.info(f"Found {total} total {self.product_type}")
		offset = 0

		while offset < total:
			logging.info(f"Processing {self.product_type} {offset + 1} to {offset + self.product_limit}")
			
			if offset > 0:
				self._save_data()
			
			url = self.build_top_products_url(offset=offset, limit=self.product_limit)
			response = self.send_request(url)
			
			for i,item in enumerate(response.json()["data"]["items"]):
				product_name = item["title"]
				logging.info(f"Fetching {self.product_type[:-1]} {i+offset+1}/{total}: {product_name}")
				
				product, reviews = self.fetch_product(product_name, single_title=False)
				if product:
					self.product_list.append(product)
					self.review_list.extend(reviews)
				else:
					logging.warning(f"Failed to fetch {self.product_type[:-1]}: {product_name}")
		
			offset += self.product_limit

		logging.info(f"Scraped {len(self.product_list)} {self.product_type} total")
	
		self._save_data()
	
		return self.product_list, self.review_list

	def fetch_product_list(self, product_list):
		"""
		Fetches products and their reviews based on a custom list of product titles.

		Args:
			product_list (List[str]): A list of product titles.

		Returns:
			Tuple[List[dict], List[dict]]: Lists of product and review data.
		"""
		self.product_list = []
		self.review_list = []
		
		logging.info(f"Fetching {len(product_list)} {self.product_type} from the list")

		for i,product in enumerate(product_list):
			logging.info(f"Fetching {self.product_type[:-1]} {i+1}/{len(product_list)}: {product}")
			
			product, reviews = self.fetch_product(product, single_title=False)
			
			if product:
				self.product_list.append(product)
				self.review_list.extend(reviews)
			else:
				logging.warning(f"Failed to fetch {self.product_type[:-1]}: {product}")

		self._save_data()

		return self.product_list, self.review_list

	def fetch_top_products(self, limit=10, sort_by="-metaScore", year_min=1900):
		"""
		Fetches the top-rated products based on specified criteria.

		Args:
			limit (int): Number of top products to fetch.
			sort_by (str): Sort criteria. (metaScore, userScore, releaseDate etc.)
			year_min (int): Minimum release year.

		Returns:
			Tuple[List[dict], List[dict]]: Lists of product and review data.
		"""
		self.product_list = []
		self.review_list = []
		
		logging.info(f"Fetching top {limit} {self.product_type} sorted by {sort_by} from {year_min} to {self.current_year}")
	
		url = self.build_top_products_url(limit=limit, sort_by=sort_by, year_min=year_min)
		response = self.send_request(url)
		products = response.json()["data"]["items"]

		for i, item in enumerate(products):
			product_name = item["title"]
			logging.info(f"Fetching top {self.product_type[:-1]} {i+1}/{limit}: {product_name}")
			
			product, reviews = self.fetch_product(product_name, single_title=False)
			
			if product:
				self.product_list.append(product)
				self.review_list.extend(reviews)
			else:
				logging.warning(f"Failed to fetch {self.product_type[:-1]}: {item['title']}")

		self._save_data()
		return self.product_list, self.review_list

	def fetch_products_by_year(self, year, limit=100):
		"""
		Fetches top products released in a specific year.

		Args:
			year (int): Release year.
			limit (int): Maximum number of products to fetch.

		Returns:
			tuple: Lists of product and review data for the given year.
		"""
		self.product_list = []
		self.review_list = []
		
		logging.info(f"Fetching top {limit} {self.product_type} released in {year}")

		offset = 0
		total_fetched = 0

		while total_fetched < limit:
			url = self.build_top_products_url(limit=self.product_limit, offset=offset, year_min=year, year_max=year)
			response = self.send_request(url)
			data = response.json()["data"]

			for item in data["items"]:
				if total_fetched >= limit:
					break

				product_name = item["title"]
				logging.info(f"Fetching {self.product_type[:-1]} {total_fetched+1}/{limit}: {product_name}")
				
				product, reviews = self.fetch_product(product_name, single_title=False)
				
				if product:
					self.product_list.append(product)
					self.review_list.extend(reviews)
					total_fetched += 1
				else:
					logging.warning(f"Failed to fetch {self.product_type[:-1]}: {product_name}")

			if len(data["items"]) < self.product_limit:
				break
			offset += self.product_limit

		self._save_data()

		return self.product_list, self.review_list

	def _save_data(self):
		"""
		Saves product and review data to CSV file

		Output Files:
			- data/{product_type}_{date_index}.csv
			- data/{product_type}_reviews_{date_index}.csv
		"""
		logging.info(f"Saving {self.product_type[:-1]} data to CSV")
		
		products_df = pd.DataFrame(self.product_list)
		
		products_df.drop(columns=["production"], errors="ignore", inplace=True)
		products_df.drop(products_df[products_df["id"].duplicated()].index, axis=0, inplace=True)
		products_df.to_csv(f"data/{self.product_type}.csv", index=False)
		
		logging.info(f"Saved {len(products_df)} {self.product_type} to data/{self.product_type}.csv")

		reviews_df = pd.DataFrame(self.review_list)

		reviews_df.rename(columns={"product_id": "id", "product_title": "title"}, inplace=True)
		reviews_df = reviews_df[["id", "title", "quote", "score", "date", "author", "publicationName", "review_type"]]
		reviews_df.drop_duplicates(inplace=True)
		reviews_df.to_csv(f"data/{self.product_type}_reviews.csv", index=False)
	
		logging.info(f"Saved {len(reviews_df)} reviews to data/{self.product_type}_reviews.csv")