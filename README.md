## Overview

This is a small project I completed in my own time, which involved building real-time data pipeline dashboard for London Underground’s Central Line arrivals data in a given day (08/09/2025). The aim was to extract live arrival predictions from the Transport for London (TfL) Unified API, and then transform & load the data into a PostgreSQL warehouse using Airflow; before analysing & visualising key performance metrics in Tableau.

## API

The API that I used for this project ([TfL Unified API](https://api.tfl.gov.uk/)) can be found here. It provides real-time and static data about London's public transport network, including: 

- Arrivals at stops and stations (buses, underground, overground, etc.)
- Line status (delays, closures, service updates)
- Vehicle locations for certain lines

Within the API, there is also other useful static data which provides information pertaining to stations, lines, routes and platforms (for example: names, geographic coordinates, etc..). I chose the TfL Unified API for this project, primarily because of the ability to track real-time insights - specifically, arrivals on a certain line live, which would enable me to build ETL pipelines reflecting current transit and mirror a real-world business use case. Furthermore, as it includes all lines, stops, and vehicles in London, this allows for both line-specific and network-wide analysis. The API itself is also frequently updated, which rendered it a suitable choice for this task.

## Scope

For this task, I made the decision to focus exclusively on the Central line of the London Underground instead of importing data from every line. This was due to tube strikes affecting other lines, which led to reduced service or suspensions, making their data less reliable for analysis. Limiting the data to a single line allowed for clearer analysis and more meaningful visualizations, without being overwhelmed by inconsistent data from other lines. It also improved the performance of the ETL pipeline and subsequent database operations, ensured compliance with TfL API rate limits, and kept the project manageable and easy to interpret.

If I were to expand the project to multiple lines without comprising the pipeline's performance, I would consider techniques such as parallelization - specifically when making HTTP requests to API to speed up data extraction while respecting API rate limits. I would implement batch requests (fetch arrivals for a subset of stops or lines at a time, rather than all at once, to avoid overwhelming the API and my pipeline).

## ETL process

1. **Extract**:
Pulled stop information and live arrivals from the TfL Unified API. Each stop includes its ID, name, and location; each arrival includes vehicle, route, expected arrival, direction, and platform details. A small delay was added between API calls to avoid hitting TfL rate limits.

Data is collected from the TfL Unified API using two key endpoints:

**Stops**: `https://api.tfl.gov.uk/Line/{lineId}/StopPoints`
This returns all stations/stop points for the specified line, including stop ID, name, and coordinates.

**Arrivals**: `https://api.tfl.gov.uk/StopPoint/{stopPointId}/Arrivals`
This endpoint returns real-time arrival predictions for a given stop point, including vehicle ID, line, direction, platform, and expected arrival time.

2. **Transform**:
I cleaned and shaped the raw API data into the desired schema, whilst standardizing column names and data types as needed. This phase included deriving features such as `minutes_to_arrival`, `stop_name` and `direction` to allow for geospatial analysis; whilst other fields collected such as `hour` and `weekday` may allow for time-series based analysis in the future.

I also removed duplicate arrivals to ensure accuracy for data analysis.

3. **Load**:

Final step of the pipeline writes the transformed arrival data into a PostgreSQL warehouse, using the SQLAlchemy ORM/core library to manage database connections and queries. A SQLAlchemy engine is created from the PostgreSQL connection string - this engine manages pooled connections to the database efficiently. Before loading data, the pipeline calls `metadata.create_all(conn)` to ensure the table exists with the correct schema. This makes the process idempotent (safe to run repeatedly).

4. **Orchestration**:

The entire ETL pipeline is orchestrated with Apache Airflow. The pipeline is defined as an Airflow DAG; the tasks to be completed (extract, transform and load the data) are defined and linked together in sequence.

The DAG runs on a 5-minute interval, continuously pulling fresh arrival predictions for the Central line. Each stage of the pipeline (get stops → fetch arrivals → transform → load) runs as a separate Airflow task. Any failures for a task are also logged, making debugging easier. 

The tasks are also configured with retries and delays, so any transient API failures (such as network issues, lack of responsiveness from TfL endpoint) don’t break the pipeline.

## Dashboard

The final output of this project was an interactive Tableau dashboard that summarizes Central Line service performance, looking at different service KPIs that answer important questions about performance, on a given day. Because connection directly to PostgreSQL is not supported in Tableau Public, the data was exported from the database into CSV files using psql commands and then imported into Tableau. This ensured that the dashboard reflects the processed and transformed dataset created by the ETL pipeline.

The visualizations that my dashboard comprises of include:

**Distribution of Passenger Wait Times (by Direction)**:

The histogram breaks down passenger wait times into bins, with colors showing different destinations such as Epping, Hainault, and West Ruislip. This visualization helps identify which branches of the Central Line consistently experience longer waits. The visualization shows that the bulk of arrivals cluster in the first 15 minutes, which is typical for metro systems. However, there are still notable counts stretching into the 20–25+ minute range, which are clear signs of extended delays (likely due to the tube strikes at the time of data extraction).

In particular,  Bethnal Green (light blue) and Epping (green) stand out as frequently contributing to longer wait times (10–20 minutes). Hainault (yellow-brown) shows a strong presence in the 15–20+ minute bins, suggesting clear under-servicing of this branch. Directions like White City or West Ruislip appear less frequently, possibly reflecting fewer trains overall or better service reliability. The right-hand side of the chart is dominated by Hainault and Bethnal Green, indicating that these directions are disproportionately impacted when service gaps occur.

This visualization helps us answer important questions - such as:
- Which branches/directions suffer longer waits?
- Are delays spread evenly across the line or concentrated in certain routes?

Based on this visualization, a recommendation to TfL could be to rebalance train dispatch schedules to ensure that under-served branches (like Hainault/Epping) get more even service coverage.

<img width="1374" height="729" alt="image" src="https://github.com/user-attachments/assets/c22bb0bf-f980-4115-bbcc-80e3318efdca" />


**Geospatial Map (Distribution of Train Arrival Delays)**:

The map plots stations geographically and colors them according to the severity of delays. This helps identify spatial patterns across the Central Line network - but more specifically, geographic weak points in Central Line operations. Other factors which may be considered here are:
- Which branches consistently underperform? This helps TfL prioritize interventions.
- Whether delays are evenly spread or concentrated in specific sections of the line.

The colour denotes the average wait time (blue = early/short waits, red = long delays), and size represents volume of arrivals recorded.

The eastern branches (Hainault loop, Epping, Fairlop) are strongly red, meaning longer wait times are concentrated there. Central London stations (closer to Oxford Circus, Holborn, etc.) are lighter, sometimes even showing early arrivals (slight blue). The cluster of large, deep red circles on the loop shows systemic delays, not isolated cases; consistent with the observations for the histogram visualization. This shows that the Hainault loop is clearly a hotspot.

However, larger dots (more arrivals recorded) don’t necessarily mean better service. For example, Bethnal Green and surrounding stops have both high arrival counts and long delays, suggesting that busy areas are not being served enough.

Recommendations for TfL based on this visualization would be as follows:
- Prioritize service balancing on the eastern branches (Hainault, Epping), which consistently show longer waits.
- Investigate whether delays are due to train allocation issues, geographic bottlenecks (e.g., at Leytonstone where the line splits), or infrastructure issues.
- Use geographic, real-time monitoring to redirect trains dynamically to areas where delays are prominent, instead of applying a uniform schedule.

<img width="1606" height="748" alt="image" src="https://github.com/user-attachments/assets/5a9d964d-e11b-47c5-bd38-21aa99ae04fe" />

**Average Wait Times by Platform**:

This stacked bar chart shows average wait Times by platform across the Central Line. Each bar represents a platform, with the length indicating average wait time (in minutes) and colour ranging from green (short waits) to red (long waits).

This viz can help answer crucial questions such as:
- Which specific platforms are underperforming, rather than just entire stops.
- Whether delays are directional (e.g., eastbound heavier than westbound).
- The degree of consistency across the network, by highlighting both severely delayed and well-performing platforms.

What can be observed from the chart is that some platforms average just a few minutes wait (e.g., Eastbound Platform 2/3, Inner Rail Platform -0.59 minutes), while others exceed 17–18 minutes (e.g., Eastbound Platform at 18.24 minutes) - this shows high variability and unpredicability between platforms. Thee are also outliers with very large delays; platforms like the Inner Rail Platform (17.40 minutes) and certain Eastbound platforms (18.24 minutes) show significant delays compared to the rest. These are bottleneck points that may reflect scheduling or capacity issues.

A few platforms (e.g., Inner Rail Platform -0.59, Westbound Platform -0.64) even show slight early arrivals, meaning trains often reach before the expected time. Eastbound and certain outer rail platforms consistently have higher wait times compared to westbound or inner rail platforms.

In order to be able to best utilise this visualization to their advantage; TfL may wish to carry out further investigation into whether platform congestion, train turnaround times, or scheduling variances cause these longer waits. The chart also suggests that focusing operational improvements on problematic eastbound and inner rail platforms, which show consistently higher wait times would be most beneficial - for example, rebalance train dispatch frequencies between eastbound and westbound to reduce disparities in delays.

<img width="1614" height="750" alt="image" src="https://github.com/user-attachments/assets/3e03b11e-4723-4fa5-a376-040486a942da" />


**Platform Traffic Treemap**

This visualization is a treemap of platform traffic. Each rectangle represents a platform, where the size is equivalent total number of train arrivals (traffic handled), and colour represents average wait time (where blue = shorter waits, red = longer waits). I chose to focus on the top 10 platforms with the heaviest traffic. 

This helps us to identify:
- Which platforms are the busiest across the network?
- Where does high traffic coincides with long wait times? This would suggest operational bottlenecks.
- Which quieter platforms might be able to absorb extra load if scheduling is adjusted?

We can observe that there is an uneven distribution of traffic, with certain platforms (Inner Rail - Platform 2, Eastbound - Platform 2) bearing the brunt of the load, while Westbound Platform 3 and Eastbound Platform 6 remain idle despite delays. The delays on empty platforms (12.20 and 10.85 minutes) suggest potential inefficiencies, such as trains being scheduled but not arriving, or platforms being reserved but not utilized effectively. The busiest platforms appear to be Inner Rail - Platform 2 and Eastbound - Platform 2, indicated by the darkest orange shades, suggesting the highest traffic or longest average wait times (up to 24.28 minutes). Less-busy platforms that could absorb extra footfall include Westbound - Platform 3 and Eastbound - Platform 6, which are observed as smaller squares, with delays of 12.20 and 10.85 minutes respectively. These platforms appear underutilized and could handle redirected traffic with adjusted scheduling.

Based on this data, TfL may wish to:
- Redirect some traffic from the busiest platforms (Inner Rail - Platform 2, Eastbound - Platform 2) to Westbound Platform 3 and Eastbound Platform 6 to balance the load and reduce congestion.
- Investigate the causes of delays on Westbound Platform 3 and Eastbound Platform 6. In particular, it may be worth revising timetables to ensure these platforms are actively used, minimizing idle time.
- A further investigation may be required to assess whether Westbound Platform 3 and Eastbound Platform 6 are being adequately maintained or if there are underlying issues preventing their use.

Platform usage would need to be regularly monitored, along with patterns in platform delays to adjust resource allocation.

Note that Westbound Platform 3 and Eastbound Platform 6 represent the empty squares in the image below, with delays of 12.20 and 10.85 minutes respectively

<img width="1387" height="556" alt="image" src="https://github.com/user-attachments/assets/369f3eb0-6500-4c7f-8e60-1200f7add91a" />

**Average Wait Times by Stop (Bar Chart)**

The chart displays average wait times in minutes across various stops, with red indicating longer waits and green indicating shorter or negative waits (where the tube arrives earlier than scheduled). The chart is sorted in descending order - where stations with longer delays appear at the top of the chart.

This visualization can help us answer the following:
- Which stops have the longest average wait times?
- Which stops have the shortest average wait times?
- How do wait times vary across different stops on the network?
- Are there any stops with unusually high or low wait times that might indicate operational issues? And in doing so, can we identify potential areas for improving service efficiency based on wait times?

Based on the visualization, we can observe that Bethnal Green (19.18 minutes), Hainault (16.84 minutes), and Fairlop (15.73 minutes) clearly have the longest average wait times, as these bars are at the top of the chart - indicating longer waits. On the other hand, Shepherd's Bush shows a negative wait of -5.37 minutes (green bar), and Tottenham Court at 0.13 minutes, indicating that tubes often reach those stations earlier than timetabled.

The extreme values stand out: Stops like Bethnal Green, Hainault, and Fairlop show significant delays compared to the rest, suggesting potential bottlenecks or capacity issues. This chart suggests that TfL should clearly focus operational improvements on stops with the longest waits (e.g., Bethnal Green, Hainault) to address potential bottlenecks, such as insufficient train frequency or overcrowding, and consider increasing service capacity. It would also be worth possibly redistributing service resources from less busy stops (e.g., Marble Arch at 3.14 minutes) to heavily delayed areas to reduce variance.

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/d6597c72-63dc-4fcf-ab1a-b95de05f344c" /> <img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/1f1da2fb-3a5f-48f5-b89a-74bcb84b6bf7" />


**Headline KPIs**

On the top of the dashboard, I chose to highlight three important service KPIs; average wait time, % on time and worst stops (ranked in descending order based on average wait times). I selected Average Wait Time as a key metric because it directly reflects passenger experience and service reliability, providing a clear indicator of how long people wait at each stop. The use of the accompanying visualizations reflect this variability effectively across all stops, making it easy to spot trends and outliers. Additionally, I chose % On Time to assess punctuality, as it complements wait time by showing how often the service meets its scheduled targets. These metrics were chosen to offer a comprehensive view of both operational efficiency and customer satisfaction, aligning with TfL’s goals of improving service quality.

The headline metrics show that the average passenger wait time on the Central Line is around 9.95 minutes, while only about 20% of trains are classified as on time. This helps identify the overall reliability of the service at a glance. The low percentage of on-time trains highlights a systemic punctuality issue, suggesting that delays are not isolated but widespread. Furthermore, the significant gap between the average wait time and the on-time percentage indicates potential inconsistencies in service delivery, due to irregular train intervals and external factors like maintenance schedules - both of which were caused by the tube strikes that week.

Below is an image of the final dashboard.

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/347fd9e0-e2b2-4803-b620-8d3aab9a30c8" />


## Considerations for Future Work

At the moment, I have only run the ETL pipeline throughout the space of one day; which has limited the scope of my data storytelling and ability to extract insights from the data. In order to be able to draw more vivid patterns from the data, I would consider running the pipeline over a more extended period (e.g throughout the week) to allow for time-series based analysis. External factors also affected this task; the current ETL pipeline focuses on the Central Line due to tube strikes affecting other lines, which reduced service or suspended operations elsewhere. To handle multiple lines in the future, I would implement parallelization for HTTP requests to the TfL API, using threading to speed up the extraction phase of the pipeline while not exceeding the API rate limits.

As mentioned above, I may also expand the extract_data function to process stops in batches (e.g., 10 stops at a time) rather than individually, reducing API calls and improving pipeline performance. 

If I were to perform time-series based analysis, I would enhance the visualizations further: for example, creating a heatmap showing wait times by hour and stop to identify peak congestion periods, using hours from the transformed data. This would enable me to understand daily usage patterns better, and would also highlight when delays are most severe. Another possible visualization for the future could be a line graph of average wait times over weeks or months to visualize long-term trends, helping to illustrate the impact of strikes or seasonal changes.

## How to run:

**Prerequisites:**

- Ensure you have Python 3.6 or higher installed.
- Install required libraries using pip:
  
`pip install requests pandas sqlalchemy psycopg2-binary`

**PostgreSQL database**:

Set up a PostgreSQL database. The code assumes a connection to a database at postgres, with port 5432 with a user postgres and a password (replace ************ in DB_URI with your actual password). You will need to create a database named postgres (or update DB_URI to match your database name), and ensure the PostgreSQL server is running and accessible (e.g., locally or via a container like Docker). Also, be sure to update `docker-compose.yaml` file with your correct PostgreSQL login credentials. 

