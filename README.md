# FreeIPA MCP Server

Model Context Protocol (MCP) server for interacting with FreeIPA directory management systems.

## 📋 Overview

This MCP server provides various tools for interacting with FreeIPA identity management systems. You can perform user and group management, password operations, and system status monitoring.

## 🚀 Features

### User Management
- ✅ List users
- ✅ Show user details
- ✅ Add new users
- ✅ Modify user information
- ✅ Change passwords
- ✅ Reset passwords (with phone verification)

### Group Management
- ✅ List groups
- ✅ Show group details
- ✅ Add new groups
- ✅ Add members to groups
- ✅ Remove members from groups

### System Management
- ✅ Connect to FreeIPA server
- ✅ Check connection status
- ✅ Disconnect from server

## 🛠️ Installation

### Requirements

- Python 3.8+
- FreeIPA server
- FreeIPA API access

### Dependencies

```bash
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file and define the following variables:

```env
FREEIPA_SERVER=https://your-freeipa-server.com
FREEIPA_USERNAME=admin
FREEIPA_PASSWORD=your-password
FREEIPA_VERIFY_SSL=true
PORT=8000
HOST=0.0.0.0
```

## 🚀 Running

### Development Environment

```bash
python freeipa_mcp_server.py
```

### With Docker

```bash
# Build image
docker build -t freeipa-mcp-server .

# Run container
docker run -p 8000:8000 --env-file .env freeipa-mcp-server
```

### With Docker Compose

```yaml
version: '3.8'
services:
  freeipa-mcp-server:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
```

## 📚 API Endpoints

### Health Check
- `GET /health` - System status and connection information

### Connection Status
- `GET /connection-status` - FreeIPA connection status

### MCP Endpoints
- `GET /sse` - Server-Sent Events endpoint
- `POST /messages` - MCP message endpoint

## 🔧 MCP Tools

### Connection Management

#### `freeipa_connect`
Connect to FreeIPA server.

```python
{
  "server": "https://freeipa.example.com",
  "username": "admin",
  "password": "password",
  "verify_ssl": true
}
```

#### `freeipa_disconnect`
Disconnect from FreeIPA server.

#### `freeipa_status`
Check connection status.

### User Operations

#### `user_list`
Get list of users.

```python
{
  "sizelimit": 100
}
```

#### `user_show`
Show user details.

```python
{
  "uid": "john.doe"
}
```

#### `user_add`
Add new user.

```python
{
  "uid": "newuser",
  "givenname": "John",
  "sn": "Doe",
  "mail": "john.doe@example.com",
  "userpassword": "password123"
}
```

#### `user_modify`
Update user information.

```python
{
  "uid": "john.doe",
  "mail": "newemail@example.com",
  "telephonenumber": "+905551234567"
}
```

#### `change_password`
Change user password.

```python
{
  "username": "john.doe",
  "new_password": "newpassword123",
  "old_password": "oldpassword123"
}
```

#### `forgot_reset_password`
Reset password (with phone verification).

```python
{
  "username": "john.doe",
  "phone": "+905551234567",
  "new_password": "newpassword123"
}
```

### Group Operations

#### `group_list`
Get list of groups.

```python
{
  "sizelimit": 100,
  "cn": "developers",
  "description": "Development team"
}
```

#### `group_show`
Show group details.

```python
{
  "cn": "developers"
}
```

#### `group_add`
Add new group.

```python
{
  "cn": "newgroup",
  "description": "New group description"
}
```

#### `group_add_member`
Add member to group.

```python
{
  "cn": "developers",
  "user": "john.doe"
}
```

#### `group_remove_member`
Remove member from group.

```python
{
  "cn": "developers",
  "user": "john.doe"
}
```