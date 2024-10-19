# TCP_Server

Creating a Http-provisional service on a Public IP VM.

Things you would need:
1. FastApi file on a directory on the VM.
2. app.sock file in the code directory.
3. venv created for the particular directory.
4. .socket file that listens to the app.sock file (not any port number).
5. .service file that configures the service to run and use the app.sock file to
   run the FastApi in the code ( App=FastAPi(); ).
6. Nginx file for reverse proxy that listens on the same port as the service
   and attaches with the app.sock file.
7. Nginx files will be included in both sites-available and sites-enabled folder.

The code being proper running with asyncio will use uvicorn workers to run and load
balance.
