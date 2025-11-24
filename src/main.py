import os, time, logging
logging.basicConfig(filename=os.path.join(os.path.dirname(__file__), "..", "logs", "run.log"),
                    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
def main():
    logging.info("AlgoTrade run started.")
    print("Hello from AlgoTrade! Replace this with your runner/backtest.")
    logging.info("AlgoTrade run finished.")
if __name__ == "__main__":
    main()
