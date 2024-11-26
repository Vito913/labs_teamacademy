from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from bs4 import BeautifulSoup
from seleniumbase import Driver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By



def get_proxy_list(max_proxies=50):
    base_url = "https://spys.one/en/https-ssl-proxy/"

    if max_proxies == 30:
        max_proxies = "0"
    elif max_proxies == 50:
        max_proxies = "1"
    elif max_proxies == 100:
        max_proxies = "2"
    elif max_proxies == 200:
        max_proxies = "3"
    elif max_proxies == 300:
        max_proxies = "4"
        
    print(f"Starting proxy collection with max_proxies={max_proxies}")
    driver = Driver(uc=True)
    wait = WebDriverWait(driver, 10)
    
    try:
        driver.get(base_url)
        print("Loaded base URL")
        
        dropdown = wait.until(EC.presence_of_element_located((By.ID, 'xpp')))
        dropdown.click()
        print("Clicked dropdown")
        
        option = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f'#xpp option[value="{max_proxies}"]')))
        option.click()
        print(f"Selected {max_proxies} proxies option")
        
        wait.until(EC.staleness_of(dropdown))
        time.sleep(3)  # Increased wait time
        
        selected_value = driver.find_element('css selector', '#xpp option[selected]').get_attribute('value')
        print(f"Current selected value: {selected_value}")
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        proxy_rows = soup.find_all('tr', attrs={'class': lambda x: x and ('spy1x' in x or 'spy1xx' in x)})
        
        proxies = []
        for row in proxy_rows:
            proxy_cell = row.find('font', class_='spy14')
            if proxy_cell:
                ip = proxy_cell.text.strip()
                if ':' in ip:
                    proxies.append(ip)
        
        print(f"Found {len(proxies)} proxies")
        return proxies
        
    except Exception as e:
        print(f"Error in get_proxy_list: {str(e)}")
        return []
    finally:
        try:
            driver.quit()
        except Exception as e:
            print("Error quitting driver" + str(e))
            



def test_proxy(proxy):
    try:
        driver = Driver(uc=True, proxy=proxy)
        # Set page load timeout
        driver.set_page_load_timeout(10)
        
        start_time = time.time()
        driver.get("http://example.com")  # Lighter test URL
        
        # Check if page loaded successfully
        if driver.page_source and len(driver.page_source) > 0:
            driver.quit()
            return True, proxy, time.time() - start_time
            
    except Exception as e:
        print(f"Error testing proxy {proxy}: {str(e)}")
    finally:
        try:
            driver.quit()
        except Exception as e:
            print("Error quitting driver" + str(e))
    return False, proxy, 0



def get_working_proxies(max_workers=5):
    proxies = get_proxy_list()
    working_proxies = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_proxy = {executor.submit(test_proxy, proxy): proxy for proxy in proxies}
        
        for future in as_completed(future_to_proxy):
            success, proxy, response_time = future.result()
            if success:
                print(f"Working proxy found: {proxy} (Response time: {response_time:.2f}s)")
                working_proxies.append((proxy, response_time))
    
    # Sort by response time
    return sorted(working_proxies, key=lambda x: x[1])

def save_proxies_to_file(proxies, filename='working_proxies.csv'):
    """Save working proxies to a file with their response times."""
    with open(filename, 'w') as f:
        f.write("Proxy,Response Time (s)\n")
        for proxy, response_time in proxies:
            f.write(f"{proxy},{response_time:.2f}\n")
    print(f"Saved {len(proxies)} proxies to {filename}")

if __name__ == '__main__':
    try:
        print("Starting proxy collection...")
        working_proxies = get_working_proxies(max_workers=10)  # Reduced workers
        
        if working_proxies:
            print(f"\nFound {len(working_proxies)} working proxies")
            try:
                save_proxies_to_file(working_proxies)
                print("Successfully saved proxies to file")
            except Exception as e:
                print(f"Error saving to file: {str(e)}")
            
            print("\nWorking proxies (sorted by speed):")
            for proxy, response_time in working_proxies:
                print(f"{proxy} - {response_time:.2f}s")
        else:
            print("No working proxies found")
            
    except Exception as e:
        print(f"Error in main: {str(e)}")
    finally:
        print("Program finished")