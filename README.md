# Rag project

## To run the project, follow the steps:
### Create a virtual environment and download the necessary libraries from requirements.txt
## In a .env file, you need to add 2 variables: OPENAI_API_KEY, which will store your openAI api key and LOCATION, which will store the location of the files
### Run this in terminal: `uvicorn app:app --reload`
## 
## In the ime you start it will index all the files that will be in the file specified but you can reindex them at will with the endpoint index. Also, every time there is a change, the watchdog function will reindexit, every time you add or delete files
## Use `rm -rf db` to delete the indexed files from the database.