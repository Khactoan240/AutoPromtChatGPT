# *******************************************************************************
#
# File: fake_chatgpt_api.py
#
# Initially created by Cuong Nguyen / July 2024
#
# Description:
#   Provides a fake ChatGPT API class for users to interact with as if it were a real API.
#   This implementation uses Selenium to run a browser in the background, handling interactions
#   with the ChatGPT web interface and maintaining context for conversations.

#   Users can utilize this class to simulate API calls to ChatGPT, while the underlying
#   mechanism uses Selenium to manage the browser and perform the necessary actions to
#   communicate with ChatGPT..
#
# History:
#
# 01.07.2024 / V 0.1 / Cuong Nguyen
# - Initialize
#
# *******************************************************************************
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from signal import *
import pickle
import time
import configparser
import undetected_chromedriver as uc
import os
import re
import json
import time
import random


class FakeChatGPTAPI:
    """
A fake ChatGPT API class for simulating API interactions with ChatGPT.

This class uses Selenium to control a web browser, allowing users to interact with the ChatGPT
web interface programmatically. It maintains the context of conversations and performs actions
on behalf of the user, providing a seamless API-like experience.

Methods of this class enable users to send messages, receive responses, and manage conversation
context, mimicking the behavior of a real API while leveraging the ChatGPT web interface
through Selenium.
    """

    SCRIPT_DIR:str = os.path.dirname(os.path.abspath(__file__))
    INI_FILE_PATH:str = os.path.join(SCRIPT_DIR, 'fake_chatgpt_api.ini')

    def __init__(self, config_path=""):
        """
Constructor for the FakeChatGPTAPI class.

**Arguments:**

* ``config_path``

  / *Condition*: optional / *Type*: str / *Default*: "" /

  The path to the configuration file.

**Returns:**

(*no returns*)
        """
        # Read configuration from fake_api.ini
        config = configparser.ConfigParser()
        if not config_path:
            config_path = FakeChatGPTAPI.INI_FILE_PATH
        with open(config_path, 'r', encoding='utf-8') as configfile:
            config.read_file(configfile)
        # config.read(FakeChatGPTAPI.INI_FILE_PATH)
        self.is_context_created = False

        # Extract configuration values
        user_data_dir = config.get('options', 'user-data-dir')
        os.makedirs(user_data_dir, exist_ok=True)
        profile_directory = config.get('options', 'profile-directory')
        self.driver_path: str = config.get('driver', 'driver_path')
        self.url: str = config.get('site', 'url')
        self.wait_time: int = config.getint('context', 'wait_time')
        use_chatgpt4o = config.getboolean('site', 'use_chatgpt4o')
        manual_login = config.getboolean('options', 'manual_login')
        context_content = config.get('context', 'context_content')
        headless_mode = config.getboolean('options', 'headless_mode', fallback=False)
        cookies_path = config.get('driver', 'cookies_path', fallback="")
        
        options = uc.ChromeOptions()
        if headless_mode:
            options.add_argument('--headless=new')  # Enable headless mode
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-infobars')
            options.add_argument('--window-size=1920x1080')
            options.add_argument('--start-maximized')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

            # Additional options to make headless mode more stealthy
            options.add_argument("--disable-extensions")
            options.add_argument("--proxy-server='direct://'")
            options.add_argument("--proxy-bypass-list=*")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-accelerated-2d-canvas")
            options.add_argument("--disable-accelerated-jpeg-decoding")
            options.add_argument("--disable-accelerated-mjpeg-decoding")
            options.add_argument("--disable-accelerated-video-decode")
            options.add_argument("--disable-accelerated-video-encode")
            
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument(f"--profile-directory={profile_directory}")

        self.driver: uc.Chrome = uc.Chrome(options=options)#, driver_executable_path=self.driver_path, service_args=['--quiet'])
        print("Created chrome instance successfully!")
        self.driver.get(self.url)

        # Check if the cookies file exists
        if not os.path.exists(cookies_path):
            print(f"Cookies file not found at {cookies_path}. Creating a new cookies file.")

            # Create an empty or default cookies list
            default_cookies = []

            # Write the empty cookies list to the file
            with open(cookies_path, 'w') as file:
                file.write(json.dumps(default_cookies))
        else:
            print(f"Loading cookies from {cookies_path}.")

        # Load and add cookies if the file exists or was just created
        with open(cookies_path, 'r') as file_path:
            cookies_list = json.loads(file_path.read())

        # Once on that domain, start adding cookies into the browser
        for cookie in cookies_list:
            # If domain is left in, then in the browser domain gets transformed to f'.{domain}'
            cookie.pop('domain', None)
            self.driver.add_cookie(cookie)

        if manual_login:
            print("manual_login")
            self.manual_login()
        
        self.use_4o = False
        if use_chatgpt4o and self.check_chatgpt4o():
            # check_pass = self.check_chatgpt4o()
            self.use_4o = True
            
        self.prompt_text_area: WebElement = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.ID, "prompt-textarea"))
            )
        self.send_button: WebElement = self.driver.find_element(By.CSS_SELECTOR, "button[data-testid='send-button']")
        if context_content:
            self.send_request('\n'.join(context_content.split("@")))

        self.is_context_created = True

    def __del__(self):
        """
Destructor for the FakeChatGPTAPI class.

This method is called when an instance of the FakeChatGPTAPI class is about to be destroyed.
It ensures that any necessary cleanup is performed, such as closing the Selenium browser.

**Returns:**

(*no returns*)
        """
        if self.is_context_created:
            self.delete_context();

    def is_login(self) -> bool:
        """
Check if the user is logged in to the ChatGPT web interface.

**Returns:**

  / *Type*: bool /

  True if the user is logged in, otherwise False.
        """
        button = None
        try:
            button = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="login-button"]')
            # print("Button exists.")
        except NoSuchElementException:
            pass
            # print("Button does not exist.")
        return button is None
    
    def manual_login(self):
        """
Perform a manual login to the ChatGPT web interface.

This method initiates the manual login process, allowing the user to enter their credentials
and complete any required authentication steps.

**Returns:**

(*no returns*)
        """
        input("Please log in manually and press Enter to continue...")
        # pickle.dump(self.driver.get_cookies(), open("cookies.pkl", "wb"))
        # Write out the cookies while you are logged in
        cookies_list = self.driver.get_cookies()
        with open("cookies.pkl", 'w') as file_path:
            json.dump(cookies_list, file_path, indent=2, sort_keys=True)

    def delete_context(self):
        """
Delete the current conversation context.

This method clears the conversation history, allowing for a fresh start without any previous
context affecting the new interactions.

**Returns:**

(*no returns*)
        """
        # Wait for the button element to appear and click on it if found
        try:
            button = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.XPATH, '//button[@id="radix-:r2i:" and @aria-haspopup="menu" and @aria-expanded="false" and @data-state="closed"]'))
            )
            button.click()
            
            # Wait for the "Delete" menu item to appear and click on it
            delete_menu_item = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.XPATH, '//div[@role="menuitem" and contains(@class, "text-token-text-error") and contains(text(), "Delete")]'))
            )
            delete_menu_item.click()
            
            # Wait for the popup to appear and click the "Delete" button within the popup
            delete_button_popup = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.XPATH, '//button[@class="btn relative btn-danger" and @as="button"]//div[contains(text(), "Delete")]'))
            )
            delete_button_popup.click()
            
            print("Clicked on the 'Delete' button in the popup.")
        except Exception as e:
            print(f"An error occurred: {e}")
            
        self.is_context_created = False
    
    def check_chatgpt4o(self):
        """
        Check if ChatGPT-4.0 is available.

        This method verifies the availability of ChatGPT-4.0 for use.

        **Returns:**

        / *Type*: bool /

        True if ChatGPT-4.0 is available, otherwise False.
        """
        # Wait for the element containing "3.5" and click on it if found
        chatgpt_version = None
        try:
            chatgpt_version = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, '//div[contains(text(), "ChatGPT") and span[contains(text(), "4o")]]'))
            )
        except Exception as ex:
            pass
        else:
            print("Already using chatGPT 4o.")
            return True

        try:
            chatgpt_version = WebDriverWait(self.driver, 1).until(
                EC.presence_of_element_located((By.XPATH, '//div[contains(text(), "ChatGPT") and span[contains(text(), "3.5")]]'))
            )
        except Exception as ex:
            pass

        if chatgpt_version:
            chatgpt_version.click()
            # Wait for the element containing "GPT-4o" and click on it
            try:
                gpt_4o = WebDriverWait(self.driver, self.wait_time).until(
                    EC.presence_of_element_located((By.XPATH, '//div[contains(text(), "GPT-4o") and div[contains(text(), "Newest and most advanced model")]]'))
                )
            except Exception as ex:
                print("GPT-4o not found. Use ChatGPT verion 3.5")
                return False
            else:
                gpt_4o.click()
                return True
        else:
            print("ChatGPT version not found.")
            return False

    def refresh(self):
        self.driver.refresh()
        self.prompt_text_area: WebElement = WebDriverWait(self.driver, self.wait_time).until(
                EC.presence_of_element_located((By.ID, "prompt-textarea"))
            )
        self.send_button: WebElement = self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="send-button"]')

    def upload_file(self, file_paths):
        if not self.use_4o:
            print("This function only work with ChatGPT4o")
            return False
        
        self.refresh()
        try:
            file_upload = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='file' and @multiple and @tabindex='-1' and @class='hidden' and @style='display: none;']"))
                    )
            # file_upload.clear()
            if isinstance(file_paths, list):
                file_upload.send_keys('\n'.join(file_paths))
            else:
                file_upload.send_keys(file_paths)

            WebDriverWait(self.driver, 30).until(
                EC.invisibility_of_element_located((By.XPATH, "//div[contains(@class, 'absolute inset-0 flex items-center justify-center bg-black/5 text-white')]"))
            )
        except Exception as ex:
            print(f"Upload file failed. Exception: {ex}")
            return False
        else:
            return True

    def check_conditions(self, present_css, absent_xpath, retries=4):
        """
        Check if one element is present and another is absent. Retry the check up to 4 times if the condition is not met.
        
        :param driver: The Selenium WebDriver instance.
        :param present_xpath: XPath of the element that should be present.
        :param absent_xpath: XPath of the element that should be absent.
        :param retries: Number of retries if the condition is not met.
        :return: True if the condition is met within the given retries, False otherwise.
        """
        for attempt in range(retries):
            try:
                # Check if the present element is present
                send_button = WebDriverWait(self.driver, self.wait_time).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, present_css))
                )
                # print(f"Attempt {attempt + 1}: The element with css '{present_css}' is present.")
                
                # Check if the absent element is absent
                try:
                    contgenerate_button = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, absent_xpath))
                    )
                    # print(f"Attempt {attempt + 1}: The element with xpath '{absent_xpath}' is present.")
                    # print("Continue generate...")
                    contgenerate_button.click()
                    time.sleep(1)
                    print("Continue generate...")
                    # If the absent element is found, retry
                    continue
                except TimeoutException:
                    # The absent element is not found
                    # print(f"Attempt {attempt + 1}: The element with xpath '{absent_xpath}' is absent.")
                    return send_button
            except TimeoutException:
                # print(f"Attempt {attempt + 1}: The element with xpath '{present_xpath}' is not present.")
                continue
            
            # print(f"Attempt {attempt + 1}: Condition not met, retrying...")
        
        return None
        
    def send_request(self, request: str) -> str:
        """
        Send a request to the ChatGPT web interface and receive a response.

        **Arguments:**

        * ``request``

        / *Condition*: required / *Type*: str /

        The request string to be sent to ChatGPT.

        **Returns:**

        / *Type*: str /

        The response from ChatGPT.
        """
        if self.prompt_text_area:
            # Ensure the text area is focused using JavaScript
            self.driver.execute_script("arguments[0].focus();", self.prompt_text_area)
            
            # Optionally, click on the element to ensure focus
            self.prompt_text_area.click()
            
            # Split the request into lines and send keys
            lines = request.split('\n')
            for line in lines:
                self.prompt_text_area.send_keys(line)
                self.prompt_text_area.send_keys(Keys.SHIFT, Keys.RETURN)  # Send SHIFT + RETURN for newline
            
            # Ensure the send button is enabled and click it
            self.send_button = WebDriverWait(self.driver, self.wait_time).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="send-button"]'))
            )
            
            if self.send_button.is_enabled():
                self.send_button.click()
            else:
                print("Send button is disabled.")

            max_try = 3
            while max_try > 0: 
            # Wait for the send button element to appear
                try:
                    try:
                        stop_button = WebDriverWait(self.driver, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'button[data-testid="stop-button"]'))
                        )
                    except:
                        pass
                    
                    # try:
                    #     contgenerate_button = WebDriverWait(self.driver, 5).until(
                    #         EC.presence_of_element_located((By.XPATH, '//button[contains(@class, "btn relative btn-secondary") and contains(., "Continue generating")]'))
                    #     )

                    #     contgenerate_button.click()
                    # except:
                    #     pass

                    # send_button = WebDriverWait(self.driver, self.wait_time).until(
                    #     EC.presence_of_element_located((By.CSS_SELECTOR, 'button[data-testid="fruitjuice-send-button"]'))
                    # )
                    send_button = self.check_conditions('button[data-testid="send-button"]', '//button[contains(@class, "btn relative btn-secondary") and contains(., "Continue generating")]')

                    last_answer = WebDriverWait(self.driver, self.wait_time).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div[data-message-author-role="assistant"]'))
                    )
                    last_answer = last_answer[-1]

                    self.send_button = send_button
                except Exception as ex:
                    print(ex)
                    self.click_regen()
                    max_try -= 1
                else:
                    return last_answer.text
        return last_answer.text
    
    def click_regen(self):
        """
        Click the 'Regenerate Response' button on the ChatGPT web interface.

        This method simulates a click on the 'Regenerate Response' button to request a new response
        for the current context.

        **Returns:**

        (*no returns*)
        """
        # Wait for the button with class 'btn relative btn-primary m-auto' and click on it if found
        try:
            regenerate_button = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, '//button[contains(@class, "btn relative btn-primary m-auto") and contains(., "Regenerate")]'))
            )
            regenerate_button.click()
            print("Regenerate button clicked.")
        except:
            print("Regenerate button not found.")

def extract_json(text:str) -> dict:
    """
    Extract JSON data from a given text string.

    **Arguments:**

    * ``text``

    / *Condition*: required / *Type*: str /

    The text string containing JSON data.

    **Returns:**

    / *Type*: dict /

    A dictionary representation of the extracted JSON data.
    """
    # Regular expression to match the JSON string
    json_regex = re.compile(r'{\s*"cn":.*?}', re.DOTALL)

    # Find the JSON string in the text
    match = json_regex.search(text)
    json_data = None

    if match:
        json_str = match.group()
        # print("Extracted JSON string:")
        # print(json_str)
        
        # Optionally, you can parse the JSON string into a Python dictionary
        json_data = json.loads(json_str)
    else:
        print("No suitable answer responsed.")
    return json_data

def signal_handler(sig, frame, obj):
   """
    Handle signals from the operating system.

    **Arguments:**

    * ``sig``

    / *Condition*: required / *Type*: int /

    The signal number received from the OS.

    * ``frame``

    / *Condition*: required / *Type*: frame object /

    The current stack frame.

    * ``obj``

    / *Condition*: required / *Type*: object /

    The object that is handling the signal.

    **Returns:**

    (*no returns*)
   """
   # This function will be called when a SIGINT signal (Ctrl+C) is received
   print("\nCtrl+C pressed - Cleaning up...")
   # Perform any necessary cleanup here
   # For example, call the cleanup method of the object
   del obj
   # Exit the program
   exit(0)

def random_sleep():
    sleep_time = random.uniform(0.1, 5)  # Random float between 1 and 3
    print(f"Sleeping for {sleep_time:.2f} seconds")
    time.sleep(sleep_time)

if __name__ == "__main__":
    with open("FakeChatGPTAPI/total_chunks.pkl", "rb") as f:
        total_chunks = pickle.load(f)

    with open("batch_pairs.pkl", 'rb') as f:
        batch_pairs = pickle.load(f)


    fake_api = FakeChatGPTAPI()

    for sign in (SIGABRT, SIGILL, SIGINT, SIGSEGV, SIGTERM):
      signal(sign, lambda sig, frame: signal_handler(sig, frame, fake_api))

    response_data = []
    try:
        # for i, context in enumerate(total_chunks):
        #     if i <= 120:
        #         continue
            
        #     # cn_input = f"I am creating questions to assess the ability to find relevant passages and identify answers.\
        #     #             Generate 3 medium to easy-level questions and answers in Vietnamese based on the following Vietnamese passage. Return the results in the following format:\
        #     #             [Question] What is...\
        #     #             [Answer] ...\
        #     #             Questions should be detailed, CLEAR, and ask about ONE PROBLEM. Answers MUST be SHORT from 1 to 3 words. Questions should have specific, definite answers for easy assessment.\
        #     #             If the answer is a quantity, leave it in number form. The question must be specific and clear so that the reader can find the correct passage to answer, not use the word like this, that, because participants do not see the paragraph.\
        #     #             Here is the passage: {context}."

        #     cn_input = f"I am evaluating questions for a QA task based on news articles. I already have a set of questions, but some are very general and hard to find accurate answers, while others are specific and easy to find answers. Please assess each question on a scale from 1 to 5, where 1 is a poor question (too general) and 5 is a clear question that is easy to find an accurate answer for. The data I provide is in the following format, where each line is a question-answer pair:\
        #                 Pair 1: [Question] Daniel Day-Lewis đã giành được bao nhiêu giải Oscar cho Nam diễn viên chính xuất sắc?, [Answer] 3\
        #                 Pair 2: [Question] Hỏi gì đó?, [Answer] đáp án\
        #                 The output MUST be in this format:\
        #                 [Score Pair 1] 5\
        #                 [Score Pair 2] 3"
        #     answer = fake_api.send_request(cn_input)
        #     print(f"idx: \n{i}")
        #     response_data.append(answer)

        #     if i % 10 == 0:
        #         print("batch save!")
        #         with open(f"response_data_{i//10}.pkl", 'wb') as file:
        #             pickle.dump(response_data, file)

        #     random_sleep()

        for i, context in enumerate(batch_pairs):
            if i != 15:
                continue
            
            # cn_input = f"I am creating questions to assess the ability to find relevant passages and identify answers.\
            #             Generate 3 medium to easy-level questions and answers in Vietnamese based on the following Vietnamese passage. Return the results in the following format:\
            #             [Question] What is...\
            #             [Answer] ...\
            #             Questions should be detailed, CLEAR, and ask about ONE PROBLEM. Answers MUST be SHORT from 1 to 3 words. Questions should have specific, definite answers for easy assessment.\
            #             If the answer is a quantity, leave it in number form. The question must be specific and clear so that the reader can find the correct passage to answer, not use the word like this, that, because participants do not see the paragraph.\
            #             Here is the passage: {context}."

            # cn_input = f"I am evaluating questions for a QA task based on news articles. I already have a set of questions, but some are very general and hard to find accurate answers, while others are specific and easy to find answers. Please assess each question on a scale from 1 to 5, where 1 is a poor question (too general) and 5 is a clear question that is easy to find an accurate answer for. The data I provide is in the following format, where each line is a question-answer pair:\
            #             Pair x: [Question] Daniel Day-Lewis đã giành được bao nhiêu giải Oscar cho Nam diễn viên chính xuất sắc?, [Answer] 3\
            #             Pair y: [Question] Ai là người đạt giải nhất cuộc thi này?, [Answer] An\
            #             The output MUST be in this format:\
            #             [Score Pair x] 5\
            #             [Score Pair y] 1\
            #             Here is the question-answer data: \n{context}"
            
            cn_input = f"I am evaluating QA tasks using an AI model based on news articles. The dataset contains questions and answers, but the answers still have some unnecessary elements. For example, '1000 năm' should be modified to '1000', '17,5 tỷ USD' to '17,5 tỷ', and '53 tuổi' to '53'. Your task is to remove unnecessary words (such as 'giải', 'tuổi', 'kilometers', etc.) and retain only the essential information. The data is formatted as a question-answer pair on each line: \
            Pair 1: [Question] Daniel Day-Lewis đã giành được bao nhiêu giải Oscar cho Nam diễn viên chính xuất sắc?, [Answer] 3 giải \
            Pair 2: [Question] Từ nhà Mai đến trường xa bao nhiêu kilometers?, [Answer] 5 kilometers \
            Modify the answers and return the results in the following format: \
            [Modified Answer 1] 3 \
            [Modified Answer 2] 5 \
            Here is the question-answer data: \n{context}"
            
            answer = fake_api.send_request(cn_input)
            print(f"idx: \n{i}")
            response_data.append(answer)

            if i % 10 == 0:
                print("batch save!")
                with open(f"modilied_answer_add_{i//10 *10}.pkl", 'wb') as file:
                    pickle.dump(response_data, file)

            random_sleep()

        print("final save!")
        with open(f"modilied_answer_add_{i}.pkl", 'wb') as file:
            pickle.dump(response_data, file)
            

            
    except KeyboardInterrupt:
        del fake_api
        print('interrupted!')
