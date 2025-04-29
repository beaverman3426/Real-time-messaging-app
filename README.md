# Real time messaging app

## Project Overview
This project is a real-time messaging application designed to enable fast, scalable, and reliable communication between users. The app allows multiple clients to connect via WebSockets, send messages, and receive updates in real time. It is built with a focus on performance, scalability, and simplicity.

**Tech Stack:**
- **Backend Framework**: FastAPI (Python)
- **Database**: Apache Cassandra
- **Additional Tools**: WebSockets for real-time communication, Redis (recommended for caching)

## Technology Choices

### Why FastAPI?
FastAPI is a modern, high-performance web framework for building APIs with Python. It was chosen for the following reasons:
- **Lightweight and Fast**: FastAPI is built on StarletteVOICE and Pydantic, leveraging asynchronous programming to achieve low latency and high throughput. It is one of the fastest Python frameworks, making it ideal for real-time applications.
- **Asynchronous Support**: Native support for `async`/`await` allows handling multiple WebSocket connections efficiently without blocking operations.
- **Ease of Use**: FastAPI's automatic generation of OpenAPI documentation and type-checking via Pydantic simplifies development and maintenance.
- **Scalability**: Its asynchronous nature and minimal overhead make it suitable for scaling to handle thousands of concurrent users.

### Why Apache Cassandra?
Cassandra is a distributed, NoSQL database designed for high availability and scalability, making it an excellent fit for a real-time messaging app. Here's why it was chosen:

#### Linear Scalability
Cassandra offers linear scalability, meaning performance scales predictably as nodes are added to the cluster. Netflix's research on Cassandra demonstrates its ability to handle massive workloads with minimal latency. Below is a graph from Netflix's benchmarking, illustrating Cassandra's linear scalability:

![Netflix Cassandra Scalability Graph](https://miro.medium.com/v2/resize:fit:720/format:webp/1*r2pJJZxKNktYmRN5mi5tOA.png)

#### Eventual Consistency and Masterless Architecture
Cassandra is an **AP** (Available and Partition-tolerant) database in the CAP theorem, prioritizing availability and partition tolerance over immediate consistency. This is a good fit for real-time messaging because:
- **Eventual Consistency**: In a messaging app, it’s acceptable if messages are delivered with slight delays (e.g., User B receives a message 0.7ms faster than User C). The relaxed ACID compliance is not a drawback since precise, immediate consistency isn’t critical for this use case (You obviously wouldn't use this for a banking service as an example).
- **Masterless Design**: Cassandra operates with a peer-to-peer architecture where all nodes are equal. Data is distributed across nodes using a **consistent hashing** algorithm, forming a **ring topology**. Each node is responsible for a portion of the data, determined by a hash of the partition key. This eliminates single points of failure and ensures high availability.

#### Tunable Consistency
Cassandra allows **tunable consistency** through replication factors and consistency levels. For example:
- A replication factor of 3 means data is stored on three nodes.
- Consistency levels (e.g., `QUORUM`, `ONE`, or `ALL`) can be adjusted per query to balance performance and reliability. For messaging, a lower consistency level like `ONE` can prioritize speed while still ensuring data is eventually replicated.

#### High Write Performance
Cassandra excels in write-heavy workloads, which is critical for a messaging app where users frequently send messages. Its log-structured storage engine ensures fast writes by appending data sequentially, minimizing disk I/O.


## Cassandra Partitioning Strategy for Message Storage


The relevant table schema:

```sql
CREATE TABLE IF NOT EXISTS messages_by_conversation (
    convo_id text,
    bucket_month text,
    timestamp timestamp,
    user text,
    text text,
    PRIMARY KEY ((convo_id, bucket_month), timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC);
```

### Why This Schema?

#### 1. **Partition Key Design**

The **partition key** is composed of `(convo_id, bucket_month)`. This ensures:

- Messages are grouped by **conversation** and **month**.
- Writes and reads are scoped to manageable-sized partitions.
- Prevents any one partition (i.e., a conversation with heavy traffic) from growing too large and overwhelming a single node.

> **Why is this critical?**  
Cassandra partitions are designed to be efficient when they stay under a certain size — typically under **100MB**. Exceeding this can lead to degraded performance, hotspotting, and even out-of-memory errors on the node responsible for that partition.

#### 2. **Time Bucketing (bucket_month)**

The `bucket_month` field (e.g., `2025-04`) is used to **segment time** into monthly buckets. This:

- Prevents unbounded partition growth for long-lived conversations.
- Distributes data more evenly across the cluster.
- Enables efficient queries like “get all messages from April 2025 in convo XYZ”.

Without bucketing, a single hot partition could contain years of data and become a performance bottleneck.

---

### Importance of a Good Partition Key

A good partition key is **crucial** for any distributed system like Cassandra that aims to scale horizontally. It:

- Balances data evenly across nodes.
- Ensures query efficiency.
- Avoids hot nodes that get overwhelmed with read/write traffic.

---


# Rate Limiter

To prevent abuse and ensure fair usage, the app implements a **sliding window rate limiter**, restricting users to **5 messages per 1 second**. The rate limiter works as follows:

```python
# Rate limiting to 5 messages per 1 second with sliding window
times = [t for t in times if now - t < TIME_FRAME]
if len(times) >= MAX_CALLS:
    await websocket.send_text("Rate limit exceeded. Please slow down.")
    continue
times.append(now)
user_message_times[client_id] = times
save_message_to_db(msg)
```

## How It Works

The limiter tracks message timestamps for each client in a sliding window (1 second).

Messages sent within the window are counted. If the count exceeds 5, the client receives a "Rate limit exceeded" warning and cannot send more messages until the window slides.

Old timestamps are pruned to keep the window current.

---

## Why Rate Limiting?

- **Prevent Abuse**: Limits spam or malicious flooding of messages.
- **Resource Management**: Ensures the server and database are not overwhelmed by excessive requests.
- **Fairness**: Guarantees equitable access for all users.

---

## Caching with Redis

For improved scalability, Redis is recommended as a caching layer for the rate limiter. Storing rate-limiting data in Redis (an in-memory data store) reduces database load and provides sub-millisecond access times.

Redis’s atomic operations (e.g., `INCR` and `EXPIRE`) are ideal for implementing sliding window rate limiters.



---

## Parallelized Message Sending with `asyncio.gather`

To ensure efficient message delivery to all connected clients, the app uses `asyncio.gather` to parallelize WebSocket message sending. The relevant code is:

```python
send_tasks = [
    client.send_text(json.dumps({
        "text": msg.text,
        "timestamp": msg.timestamp.isoformat(),
        "user": msg.user
    }))
    for client in connected_clients
]
await asyncio.gather(*send_tasks, return_exceptions=True)
```

### How It Works

- A list of send tasks is created, one for each connected client, using a list comprehension.
- `asyncio.gather` runs all tasks concurrently, sending the message to all clients in parallel.
- The `return_exceptions=True` flag ensures that if one client fails (e.g., due to a dropped connection), other sends are not interrupted.

### Benefits

- **Performance**: Parallel execution reduces the time to broadcast messages, critical for real-time applications.
- **Scalability**: Handles large numbers of clients efficiently by leveraging Python’s asynchronous event loop.
- **Robustness**: Gracefully handles failures without blocking the entire broadcast.

---

## Conclusions

This real-time messaging app leverages **FastAPI** and **Cassandra** to deliver a lightweight, scalable, and high-performance solution.

- **FastAPI**’s asynchronous capabilities ensure low-latency WebSocket communication.
- **Cassandra**’s linear scalability, tunable consistency, and high write performance make it ideal for handling message data.
- The **sliding window rate limiter** prevents abuse.
- **Parallelized message sending** with `asyncio.gather` ensures efficient delivery.

---

## Room for Improvement

- **Redis Integration**: Fully implement Redis for caching rate-limiting data and possibly message queues to further reduce database load.
- **Advanced Rate Limiting**: Introduce dynamic rate limits based on user roles or server load.
- **Monitoring and Metrics**: Integrate tools like Prometheus and Grafana to monitor WebSocket connections, message throughput, and database performance.
- **Security**: Implement end-to-end encryption for messages and add authentication mechanisms to secure WebSocket connections.
- **Load Testing**: Conduct stress tests to validate performance under high user loads and optimize configurations accordingly.

By addressing these areas, the app can become even more robust, secure, and scalable for production use.
