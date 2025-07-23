# Azure Databricks PySpark Kafka Streaming
# ===========================================
# This script demonstrates how to implement real-time data streaming using Apache Kafka with PySpark in Azure Databricks.
#
# Prerequisites:
# - Azure Databricks cluster with Databricks Runtime 10.4 LTS or higher
# - Kafka cluster (Azure Event Hubs or standalone Kafka)
# - Required libraries installed on the cluster

# %md
# ## 1. Install Required Libraries
# First, install the necessary libraries. In a Databricks cluster, you can install these via the cluster libraries UI:
# - Maven library: org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0
# - PyPI packages: kafka-python, confluent-kafka (optional)

# COMMAND ----------

# Import Required Libraries
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
import json
import time
from datetime import datetime

# Initialize Spark session (usually pre-configured in Databricks)
spark = SparkSession.builder \
    .appName("KafkaStreaming") \
    .getOrCreate()

# Set log level to reduce verbose output
spark.sparkContext.setLogLevel("WARN")

print(f"Spark version: {spark.version}")
print(f"Spark session started at: {datetime.now()}")

# COMMAND ----------

# %md
# ## 2. Kafka Configuration
# Configure your Kafka connection parameters. Update these values according to your Kafka setup.

# COMMAND ----------

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = "your-kafka-broker:9092"  # Replace with your Kafka broker
KAFKA_TOPIC = "sensor-data"  # Replace with your topic name
KAFKA_GROUP_ID = "databricks-consumer-group"

# For Azure Event Hubs (if using Event Hubs as Kafka)
# KAFKA_BOOTSTRAP_SERVERS = "your-eventhub-namespace.servicebus.windows.net:9093"
# KAFKA_SASL_MECHANISM = "PLAIN"
# KAFKA_SECURITY_PROTOCOL = "SASL_SSL"
# CONNECTION_STRING = "Endpoint=sb://your-namespace.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=your-key"

print(f"Kafka Bootstrap Servers: {KAFKA_BOOTSTRAP_SERVERS}")
print(f"Kafka Topic: {KAFKA_TOPIC}")

# COMMAND ----------

# %md
# ## 3. Define Data Schema
# Define the schema for the incoming data. This example assumes JSON sensor data.

# COMMAND ----------

# Define schema for incoming JSON data
sensor_schema = StructType([
    StructField("sensor_id", StringType(), True),
    StructField("timestamp", TimestampType(), True),
    StructField("temperature", DoubleType(), True),
    StructField("humidity", DoubleType(), True),
    StructField("pressure", DoubleType(), True),
    StructField("location", StringType(), True)
])

print("Schema defined for sensor data:")
sensor_schema.printTreeString()

# COMMAND ----------

# %md
# ## 4. Create Kafka Stream Reader
# Set up the Kafka stream reader to consume messages from the Kafka topic.

# COMMAND ----------

# Create Kafka stream reader
kafka_stream = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
    .option("subscribe", KAFKA_TOPIC) \
    .option("startingOffsets", "latest") \
    .option("failOnDataLoss", "false") \
    .load()

# For Azure Event Hubs with authentication:
# kafka_stream = spark \
#     .readStream \
#     .format("kafka") \
#     .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
#     .option("subscribe", KAFKA_TOPIC) \
#     .option("kafka.sasl.mechanism", "PLAIN") \
#     .option("kafka.security.protocol", "SASL_SSL") \
#     .option("kafka.sasl.jaas.config", 
#             f'org.apache.kafka.common.security.plain.PlainLoginModule required username="$ConnectionString" password="{CONNECTION_STRING}";') \
#     .option("startingOffsets", "latest") \
#     .option("failOnDataLoss", "false") \
#     .load()

print("Kafka stream reader created successfully!")
print("Stream schema:")
kafka_stream.printSchema()

# COMMAND ----------

# %md
# ## 5. Process Kafka Messages
# Parse and transform the incoming Kafka messages.

# COMMAND ----------

# Parse JSON data from Kafka messages
parsed_stream = kafka_stream \
    .select(
        col("key").cast("string").alias("message_key"),
        col("value").cast("string").alias("json_data"),
        col("topic"),
        col("partition"),
        col("offset"),
        col("timestamp").alias("kafka_timestamp")
    ) \
    .withColumn("parsed_data", from_json(col("json_data"), sensor_schema)) \
    .select(
        col("message_key"),
        col("topic"),
        col("partition"),
        col("offset"),
        col("kafka_timestamp"),
        col("parsed_data.*")
    )

print("Message parsing configured!")
print("Parsed stream schema:")
parsed_stream.printSchema()

# COMMAND ----------

# %md
# ## 6. Apply Data Transformations
# Add business logic and transformations to the streaming data.

# COMMAND ----------

# Apply transformations and business logic
transformed_stream = parsed_stream \
    .filter(col("temperature").isNotNull()) \
    .withColumn("processing_time", current_timestamp()) \
    .withColumn("temperature_celsius", col("temperature")) \
    .withColumn("temperature_fahrenheit", (col("temperature") * 9/5) + 32) \
    .withColumn("alert_high_temp", when(col("temperature") > 30, "HIGH").otherwise("NORMAL")) \
    .withColumn("heat_index", 
                when(col("humidity").isNotNull(), 
                     col("temperature") + (col("humidity") * 0.1)).otherwise(col("temperature"))
               )

print("Data transformations applied!")

# COMMAND ----------

# %md
# ## 7. Windowed Aggregations
# Perform time-based aggregations on the streaming data.

# COMMAND ----------

# Windowed aggregations - 5-minute windows with 1-minute slides
windowed_aggregations = transformed_stream \
    .withWatermark("timestamp", "10 minutes") \
    .groupBy(
        window(col("timestamp"), "5 minutes", "1 minute"),
        col("sensor_id"),
        col("location")
    ) \
    .agg(
        avg("temperature").alias("avg_temperature"),
        max("temperature").alias("max_temperature"),
        min("temperature").alias("min_temperature"),
        avg("humidity").alias("avg_humidity"),
        avg("pressure").alias("avg_pressure"),
        count("*").alias("record_count")
    ) \
    .select(
        col("window.start").alias("window_start"),
        col("window.end").alias("window_end"),
        col("sensor_id"),
        col("location"),
        col("avg_temperature"),
        col("max_temperature"),
        col("min_temperature"),
        col("avg_humidity"),
        col("avg_pressure"),
        col("record_count")
    )

print("Windowed aggregations configured!")

# COMMAND ----------

# %md
# ## 8. Output Configuration
# Configure output sinks for the processed streaming data.

# COMMAND ----------

# Define output paths
DELTA_TABLE_PATH = "/tmp/delta/sensor_data"  # Update with your desired path
CHECKPOINT_PATH = "/tmp/checkpoints/sensor_data"  # Update with your checkpoint path
AGGREGATIONS_TABLE_PATH = "/tmp/delta/sensor_aggregations"
AGGREGATIONS_CHECKPOINT_PATH = "/tmp/checkpoints/sensor_aggregations"

# Console output for real-time monitoring (for testing/debugging)
console_query = transformed_stream \
    .select("sensor_id", "timestamp", "temperature", "humidity", "alert_high_temp") \
    .writeStream \
    .outputMode("append") \
    .format("console") \
    .option("truncate", False) \
    .option("numRows", 10) \
    .trigger(processingTime="30 seconds") \
    .queryName("console_output")

# Delta Lake output for transformed data
delta_query = transformed_stream \
    .writeStream \
    .outputMode("append") \
    .format("delta") \
    .option("checkpointLocation", CHECKPOINT_PATH) \
    .option("path", DELTA_TABLE_PATH) \
    .trigger(processingTime="1 minute") \
    .queryName("delta_output")

# Delta Lake output for aggregated data
aggregations_query = windowed_aggregations \
    .writeStream \
    .outputMode("append") \
    .format("delta") \
    .option("checkpointLocation", AGGREGATIONS_CHECKPOINT_PATH) \
    .option("path", AGGREGATIONS_TABLE_PATH) \
    .trigger(processingTime="2 minutes") \
    .queryName("aggregations_output")

print("Output streams configured!")
print(f"Delta table path: {DELTA_TABLE_PATH}")
print(f"Aggregations table path: {AGGREGATIONS_TABLE_PATH}")

# COMMAND ----------

# %md
# ## 9. Start Streaming Jobs
# Start the streaming queries to begin processing data.

# COMMAND ----------

# Start streaming queries
print("Starting streaming jobs...")

# Start console output (for monitoring)
console_stream = console_query.start()
print("✓ Console output stream started")

# Start Delta Lake output
delta_stream = delta_query.start()
print("✓ Delta Lake raw data stream started")

# Start aggregations output
aggregations_stream = aggregations_query.start()
print("✓ Delta Lake aggregations stream started")

print("\nAll streaming jobs are now running!")
print("Monitor the progress in the next cells...")

# COMMAND ----------

# %md
# ## 10. Monitor Streaming Jobs
# Monitor the status and progress of your streaming jobs.

# COMMAND ----------

# Monitor streaming progress
def print_stream_status():
    active_streams = spark.streams.active
    print(f"Number of active streams: {len(active_streams)}")
    print("-" * 50)
    
    for stream in active_streams:
        print(f"Stream ID: {stream.id}")
        print(f"Name: {stream.name}")
        print(f"Status: {stream.status}")
        
        # Get latest progress
        progress = stream.lastProgress
        if progress:
            print(f"Input rows/sec: {progress.get('inputRowsPerSecond', 'N/A')}")
            print(f"Processed rows/sec: {progress.get('processedRowsPerSecond', 'N/A')}")
            print(f"Batch duration: {progress.get('durationMs', {}).get('triggerExecution', 'N/A')} ms")
        print("-" * 30)

# Check initial status
print_stream_status()

# COMMAND ----------

# Check streaming metrics periodically
def monitor_streams(iterations=5, wait_time=30):
    """Monitor streaming metrics for specified iterations"""
    for i in range(iterations):
        print(f"\n=== Monitoring Iteration {i+1} ===")
        print_stream_status()
        
        # Wait before next check (except for last iteration)
        if i < iterations - 1:
            print(f"Waiting {wait_time} seconds for next check...")
            time.sleep(wait_time)

# Run monitoring (uncomment to execute)
# monitor_streams(3, 30)

# COMMAND ----------

# %md
# ## 11. Query Processed Data
# Query the Delta tables to verify data is being processed correctly.

# COMMAND ----------

# Read from Delta table to verify data is being written
def check_raw_data():
    try:
        raw_data_df = spark.read.format("delta").load(DELTA_TABLE_PATH)
        count = raw_data_df.count()
        print(f"Raw data table record count: {count}")
        
        if count > 0:
            print("\nSample raw data:")
            raw_data_df.orderBy(col("timestamp").desc()).limit(5).show(truncate=False)
            
            # Show data distribution by sensor
            print("\nData distribution by sensor:")
            raw_data_df.groupBy("sensor_id").count().show()
        else:
            print("No data found in raw data table yet. This is normal if streaming just started.")
            
    except Exception as e:
        print(f"Raw data table not yet available: {e}")

# Check aggregations table
def check_aggregated_data():
    try:
        agg_data_df = spark.read.format("delta").load(AGGREGATIONS_TABLE_PATH)
        count = agg_data_df.count()
        print(f"Aggregations table record count: {count}")
        
        if count > 0:
            print("\nSample aggregated data:")
            agg_data_df.orderBy(col("window_start").desc()).limit(5).show(truncate=False)
        else:
            print("No data found in aggregations table yet. This is normal if streaming just started.")
            
    except Exception as e:
        print(f"Aggregations table not yet available: {e}")

# Run data checks
check_raw_data()
check_aggregated_data()

# COMMAND ----------

# %md
# ## 12. Data Quality Checks
# Perform basic data quality checks on the streaming data.

# COMMAND ----------

# Data quality checks
def perform_data_quality_checks():
    try:
        df = spark.read.format("delta").load(DELTA_TABLE_PATH)
        
        if df.count() == 0:
            print("No data available for quality checks yet.")
            return
            
        print("=== Data Quality Report ===")
        
        # Basic statistics
        total_records = df.count()
        unique_sensors = df.select('sensor_id').distinct().count()
        print(f"Total records: {total_records}")
        print(f"Unique sensors: {unique_sensors}")
        
        # Null checks
        null_counts = df.select(
            sum(when(col("sensor_id").isNull(), 1).otherwise(0)).alias("null_sensor_id"),
            sum(when(col("temperature").isNull(), 1).otherwise(0)).alias("null_temperature"),
            sum(when(col("humidity").isNull(), 1).otherwise(0)).alias("null_humidity"),
            sum(when(col("timestamp").isNull(), 1).otherwise(0)).alias("null_timestamp")
        ).collect()[0]
        
        print("\nNull value counts:")
        for field in null_counts.asDict():
            print(f"  {field}: {null_counts[field]}")
        
        # Temperature range check
        temp_stats = df.select(
            min("temperature").alias("min_temp"),
            max("temperature").alias("max_temp"),
            avg("temperature").alias("avg_temp")
        ).collect()[0]
        
        print(f"\nTemperature statistics:")
        print(f"  Min: {temp_stats['min_temp']:.2f}°C")
        print(f"  Max: {temp_stats['max_temp']:.2f}°C")
        print(f"  Avg: {temp_stats['avg_temp']:.2f}°C")
        
        # Alert distribution
        alert_dist = df.groupBy("alert_high_temp").count().collect()
        print("\nAlert distribution:")
        for row in alert_dist:
            print(f"  {row['alert_high_temp']}: {row['count']}")
        
        # Data freshness check
        latest_timestamp = df.select(max("timestamp")).collect()[0][0]
        if latest_timestamp:
            print(f"\nLatest data timestamp: {latest_timestamp}")
            
    except Exception as e:
        print(f"Error performing data quality checks: {e}")

# Run quality checks
perform_data_quality_checks()

# COMMAND ----------

# %md
# ## 13. Stream Management
# Utilities for managing streaming jobs.

# COMMAND ----------

# Stream management functions
def stop_all_streams():
    """Stop all active streaming queries"""
    active_streams = spark.streams.active
    print(f"Stopping {len(active_streams)} active streams...")
    
    for stream in active_streams:
        print(f"Stopping stream: {stream.name} (ID: {stream.id})")
        stream.stop()
    
    print("All streams stopped!")

def restart_streams():
    """Restart all streaming queries"""
    stop_all_streams()
    time.sleep(5)  # Wait a bit before restarting
    
    print("Restarting streams...")
    # Restart the streams
    console_stream = console_query.start()
    delta_stream = delta_query.start()
    aggregations_stream = aggregations_query.start()
    
    print("Streams restarted successfully!")

def get_stream_metrics():
    """Get detailed metrics for all active streams"""
    active_streams = spark.streams.active
    metrics = []
    
    for stream in active_streams:
        progress = stream.lastProgress
        if progress:
            metrics.append({
                "name": stream.name,
                "id": stream.id,
                "batchId": progress.get("batchId", "N/A"),
                "inputRowsPerSecond": progress.get("inputRowsPerSecond", 0),
                "processedRowsPerSecond": progress.get("processedRowsPerSecond", 0),
                "triggerExecution": progress.get("durationMs", {}).get("triggerExecution", 0)
            })
    
    return metrics

# Display current metrics
print("Current stream metrics:")
for metric in get_stream_metrics():
    print(f"Stream: {metric['name']}")
    print(f"  Batch ID: {metric['batchId']}")
    print(f"  Input Rate: {metric['inputRowsPerSecond']} rows/sec")
    print(f"  Processing Rate: {metric['processedRowsPerSecond']} rows/sec")
    print(f"  Execution Time: {metric['triggerExecution']} ms")
    print()

# COMMAND ----------

# %md
# ## 14. Sample Data Producer (Optional)
# If you need to generate sample data for testing, here's a simple Kafka producer.

# COMMAND ----------

# Sample Kafka producer for testing (optional)
def create_sample_data():
    """Generate sample sensor data"""
    import random
    from datetime import datetime
    
    sensors = ["sensor_001", "sensor_002", "sensor_003", "sensor_004"]
    locations = ["Building_A", "Building_B", "Building_C", "Warehouse"]
    
    data = {
        "sensor_id": random.choice(sensors),
        "timestamp": datetime.now().isoformat(),
        "temperature": round(random.uniform(15, 35), 2),
        "humidity": round(random.uniform(30, 80), 2),
        "pressure": round(random.uniform(1000, 1020), 2),
        "location": random.choice(locations)
    }
    return json.dumps(data)

def send_sample_data_to_kafka(num_messages=100):
    """Send sample data to Kafka topic using kafka-python"""
    try:
        from kafka import KafkaProducer
        
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
            value_serializer=lambda x: x.encode('utf-8')
        )
        
        for i in range(num_messages):
            message = create_sample_data()
            producer.send(KAFKA_TOPIC, value=message)
            if i % 10 == 0:
                print(f"Sent {i} messages...")
            time.sleep(0.1)  # Send a message every 100ms
        
        producer.flush()
        producer.close()
        print(f"Sent {num_messages} sample messages to {KAFKA_TOPIC}")
        
    except ImportError:
        print("kafka-python library not installed. Install with: %pip install kafka-python")
    except Exception as e:
        print(f"Error sending sample data: {e}")

# Generate sample data (uncomment to run)
# send_sample_data_to_kafka(50)

print("Sample data producer functions are available:")
print("- create_sample_data(): Generate a single sample message")
print("- send_sample_data_to_kafka(n): Send n sample messages to Kafka")

# COMMAND ----------

# %md
# ## 15. Advanced Analytics
# Perform advanced analytics on the streaming data.

# COMMAND ----------

# Advanced analytics functions
def analyze_sensor_performance():
    """Analyze sensor performance and detect anomalies"""
    try:
        df = spark.read.format("delta").load(DELTA_TABLE_PATH)
        
        if df.count() == 0:
            print("No data available for performance analysis.")
            return
        
        print("=== Sensor Performance Analysis ===")
        
        # Sensor reliability (data frequency)
        sensor_frequency = df.groupBy("sensor_id") \
            .agg(
                count("*").alias("message_count"),
                min("timestamp").alias("first_message"),
                max("timestamp").alias("last_message")
            ) \
            .withColumn("time_span_hours", 
                       (col("last_message").cast("long") - col("first_message").cast("long")) / 3600)
        
        print("\nSensor message frequency:")
        sensor_frequency.show()
        
        # Temperature anomaly detection (simple threshold-based)
        anomalies = df.filter(
            (col("temperature") < 0) | (col("temperature") > 50) |
            (col("humidity") < 0) | (col("humidity") > 100) |
            (col("pressure") < 950) | (col("pressure") > 1050)
        )
        
        anomaly_count = anomalies.count()
        print(f"\nAnomalous readings detected: {anomaly_count}")
        
        if anomaly_count > 0:
            print("Sample anomalies:")
            anomalies.select("sensor_id", "timestamp", "temperature", "humidity", "pressure") \
                    .limit(10).show()
        
        # Location-based statistics
        location_stats = df.groupBy("location") \
            .agg(
                avg("temperature").alias("avg_temp"),
                stddev("temperature").alias("stddev_temp"),
                count("*").alias("reading_count")
            )
        
        print("\nLocation-based temperature statistics:")
        location_stats.show()
        
    except Exception as e:
        print(f"Error in performance analysis: {e}")

# Run advanced analytics
analyze_sensor_performance()

# COMMAND ----------

# %md
# ## 16. Alerting System
# Implement a simple alerting system for critical conditions.

# COMMAND ----------

# Alerting system
def check_critical_alerts():
    """Check for critical conditions and generate alerts"""
    try:
        # Read recent data (last 10 minutes)
        current_time = datetime.now()
        ten_minutes_ago = current_time.timestamp() - 600
        
        df = spark.read.format("delta").load(DELTA_TABLE_PATH)
        
        if df.count() == 0:
            print("No data available for alert checking.")
            return
        
        recent_data = df.filter(col("timestamp") >= from_unixtime(lit(ten_minutes_ago)))
        
        print("=== Critical Alerts Check ===")
        
        # High temperature alerts
        high_temp_alerts = recent_data.filter(col("temperature") > 35)
        high_temp_count = high_temp_alerts.count()
        
        if high_temp_count > 0:
            print(f"🔥 HIGH TEMPERATURE ALERT: {high_temp_count} sensors reporting >35°C")
            high_temp_alerts.select("sensor_id", "location", "temperature", "timestamp") \
                           .orderBy(col("temperature").desc()) \
                           .show(10)
        
        # Low humidity alerts
        low_humidity_alerts = recent_data.filter(col("humidity") < 20)
        low_humidity_count = low_humidity_alerts.count()
        
        if low_humidity_count > 0:
            print(f"💧 LOW HUMIDITY ALERT: {low_humidity_count} sensors reporting <20% humidity")
        
        # Sensor offline detection (no data in last 5 minutes)
        five_minutes_ago = current_time.timestamp() - 300
        recent_sensors = recent_data.filter(col("timestamp") >= from_unixtime(lit(five_minutes_ago))) \
                                   .select("sensor_id").distinct()
        
        all_sensors = df.select("sensor_id").distinct()
        offline_sensors = all_sensors.subtract(recent_sensors)
        offline_count = offline_sensors.count()
        
        if offline_count > 0:
            print(f"📡 SENSOR OFFLINE ALERT: {offline_count} sensors haven't reported in 5+ minutes")
            offline_sensors.show()
        
        if high_temp_count == 0 and low_humidity_count == 0 and offline_count == 0:
            print("✅ All systems normal - no critical alerts")
        
    except Exception as e:
        print(f"Error checking alerts: {e}")

# Run alert check
check_critical_alerts()

# COMMAND ----------

# %md
# ## 17. Cleanup and Resource Management
# Clean up resources when you're finished with the streaming job.

# COMMAND ----------

# Cleanup functions
def cleanup_streaming_resources():
    """Clean up streaming resources"""
    print("Cleaning up streaming resources...")
    
    # Stop all streams
    stop_all_streams()
    
    print("Cleanup completed!")

def cleanup_data_tables(confirm=False):
    """Clean up Delta tables (use with caution)"""
    if not confirm:
        print("To actually delete data tables, call with confirm=True")
        print("This will remove:")
        print(f"- {DELTA_TABLE_PATH}")
        print(f"- {AGGREGATIONS_TABLE_PATH}")
        return
    
    try:
        # Remove Delta tables (use dbutils in Databricks)
        # dbutils.fs.rm(DELTA_TABLE_PATH, True)
        # dbutils.fs.rm(AGGREGATIONS_TABLE_PATH, True)
        
        print("Data tables cleaned up!")
    except Exception as e:
        print(f"Error cleaning up data tables: {e}")

def cleanup_checkpoints(confirm=False):
    """Clean up checkpoint directories (use with caution)"""
    if not confirm:
        print("To actually delete checkpoints, call with confirm=True")
        print("This will remove:")
        print(f"- {CHECKPOINT_PATH}")
        print(f"- {AGGREGATIONS_CHECKPOINT_PATH}")
        return
    
    try:
        # Remove checkpoint directories (use dbutils in Databricks)
        # dbutils.fs.rm(CHECKPOINT_PATH, True)
        # dbutils.fs.rm(AGGREGATIONS_CHECKPOINT_PATH, True)
        
        print("Checkpoints cleaned up!")
    except Exception as e:
        print(f"Error cleaning up checkpoints: {e}")

# Display cleanup options
print("Cleanup functions available:")
print("- cleanup_streaming_resources(): Stop all streaming jobs")
print("- cleanup_data_tables(confirm=True): Remove Delta tables")
print("- cleanup_checkpoints(confirm=True): Remove checkpoint directories")

# COMMAND ----------

# %md
# ## 18. Final Status and Summary

# COMMAND ----------

print("=" * 60)
print("🚀 AZURE DATABRICKS KAFKA STREAMING SETUP COMPLETE!")
print("=" * 60)

print("\n📊 Current Status:")
active_streams = spark.streams.active
print(f"Active streams: {len(active_streams)}")

for stream in active_streams:
    print(f"  - {stream.name}: {stream.status}")

print(f"\n📁 Data Locations:")
print(f"Raw data: {DELTA_TABLE_PATH}")
print(f"Aggregations: {AGGREGATIONS_TABLE_PATH}")

print(f"\n⚙️ Configuration:")
print(f"Kafka servers: {KAFKA_BOOTSTRAP_SERVERS}")
print(f"Kafka topic: {KAFKA_TOPIC}")

print(f"\n🔧 Management Commands:")
print("- print_stream_status(): Check stream status")
print("- perform_data_quality_checks(): Run data quality checks")
print("- check_critical_alerts(): Check for alerts")
print("- analyze_sensor_performance(): Run performance analysis")
print("- stop_all_streams(): Stop all streaming")
print("- cleanup_streaming_resources(): Full cleanup")

print(f"\n💡 Next Steps:")
print("1. Configure your Kafka connection parameters above")
print("2. Start sending data to your Kafka topic")
print("3. Monitor the console output and Delta tables")
print("4. Use the management functions to monitor and analyze data")
print("5. Run cleanup when finished")

print("\n✨ Happy Streaming!")

# COMMAND ----------