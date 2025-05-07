# SyncSphere

SyncSphere is a distributed file backup and sharing system designed as a final project for my highschool lessons. It allows users to register, upload/download files, manage storage quotas, and share files with friends in real time across multiple regional servers.

## Table of Contents

* [Features](#features)
* [Architecture](#architecture)
* [Prerequisites](#prerequisites)
* [Installation](#installation)
* [Configuration](#configuration)
* [API Endpoints](#api-endpoints)
* [Database Schema](#database-schema)


## Features

* 🚀 **User Authentication:** Secure registration & login with password hashing.
* 📂 **File Management:** Upload, download, rename, and delete files.
* 💾 **Storage Quota:** Track and enforce per-user storage limits.
* 🤝 **Friend System:** Send/accept friend requests to share files.
* 🌐 **Distributed Sync:** Queue-based change propagation via a grand server for redundancy.
* 🔒 **Secure Communication:** SSL/TLS sockets for inter-server sync.

## Architecture

* **Backend Framework:** Flask (Python)
* **Database:** SQLite with SQLAlchemy ORM
* **Sync Layer:** Python sockets + SSL, multi-threaded regional–grand server model
* **Queue System:** In-memory `Queue` for change events

## Prerequisites

* Python 3.8 or higher
* pip
* OpenSSL (for generating self-signed certificates)

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/eyalp7/SyncSphere.git
   cd SyncSphere
   ```
2. **Create a virtual environment & install dependencies:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Install the needed python libraries:**

   ```bash
   pip install flask
   pip install flask-wtf
   ```

## Sync Mechanism

1. **Event Generation:** On every file or friend change, an event is enqueued.
2. **Regional Sender:** Sends events over SSL socket to the grand server.
3. **Grand Server:** Receives and rebroadcasts to all other regionals.
4. **Regional Receiver:** Applies events idempotently, updating local DB.

## API Endpoints

| Method | Endpoint                   | Description             |
| ------ | -------------------------- | ----------------------- |
| POST   | `/register`                | Create a new user       |
| POST   | `/login`                   | User authentication     |
| POST   | `/logout`                  | End session             |
| POST   | `/upload`                  | Upload a file           |
| GET    | `/download/<file_id>`      | Download a file         |
| POST   | `/friends/request`         | Send a friend request   |
| POST   | `/friends/accept/<req_id>` | Accept a friend request |
| GET    | `/friends`                 | List friends            |

## Database Schema

* **users**: Stores user credentials and storage data.
* **files**: Metadata for each uploaded file.
* **friend\_requests**: Tracks pending requests.
* **friendships**: Records established friendships.


**Download the full project breakdown PDF here:**
[📄 project_breakdown.pdf](project_breakdown.pdf)

