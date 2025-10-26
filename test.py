from selenium import webdriver
from selenium.webdriver.firefox.options import Options

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0")

driver = webdriver.Firefox(options=options)
driver.get("https://www.google.com")
print("Title:", driver.title)
driver.save_screenshot("test_screenshot.png")  # Check if this file is created
driver.quit()
