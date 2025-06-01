from metacritic_scraper import MetacriticScraper
from rich import print

if __name__ == "__main__":
	scraper = MetacriticScraper(product_type="games") # product_type can be movies, games or shows
 
	#products, reviews = scraper.fetch_products_by_year(2025, 10)
	#products, reviews = scraper.fetch_all_products()
	#products, reviews = scraper.fetch_top_products(sort_by="-userScore")
	#products, reviews = scraper.fetch_product_list(["God of War Ragnarök", "The Legend of Zelda: Tears of the Kingdom"])
	products, reviews = scraper.fetch_product("Elden Ring Nightreign")

	#print(products)