import threading

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

class DistractorTaskManager:
    def __init__(self):
        self.url = "https://cairo-robotics.github.io/memory_match_game/"
        self._distractor_event = threading.Event()
        self._distractor_event.set() # set to true when distractor task is NOT running

    @property
    def distractor_active(self):
        return not self._distractor_event.is_set()

    def launch_distractor(self): # runs in timer thread
        print("Launching distractor task...")

        geckodriver_path = "/snap/bin/geckodriver"
        driver_service = webdriver.FirefoxService(executable_path=geckodriver_path)

        driver = webdriver.Firefox(service=driver_service)

        try:
            driver.get(self.url)
            driver.implicitly_wait(2)
            # driver.find_element_by_id("start").click()

            time_left = driver.find_element(By.ID, "timer")
            score = driver.find_element(By.ID, "score")

            wait = WebDriverWait(driver, timeout=2.5 * 60)
            # wait.until(lambda _ : time_left.text == "1:50")
            wait.until(lambda _ : time_left.text == "0:00")
            print("Memory match final score: " + score.text)

            driver.close()
            driver.quit()
        except Exception as e:
            print("Distractor task failed: ", e)
            driver.quit()
        

    def wait_for_completion(self): # runs in main thread
        print("Waiting for distractor task to complete...")
        self._distractor_event.wait()
        print("Distractor task completed.")

    def start_timer_and_launch(self, wait_duration=1):
        wait_duration_in_seconds = 60 * wait_duration
        # wait_duration_in_seconds = 5

        def callback():
            self._distractor_event.clear()
            self.launch_distractor()
            self._distractor_event.set()

        timer = threading.Timer(wait_duration_in_seconds, callback)
        timer.start()

if __name__ == "__main__":
    distractor_manager = DistractorTaskManager()
    distractor_manager.start_timer_and_launch(wait_duration=0)
    distractor_manager.wait_for_completion()