## Overview

This is a small project I completed in my own time, which involved building real-time data pipeline dashboard for London Underground’s Central Line arrivals data. The aim was to extract live arrival predictions from the Transport for London (TfL) Unified API, and then transform & load the data into a PostgreSQL warehouse using Airflow; before analysing & visualising key performance metrics in Tableau.

## API

The API that I used for this project ([TfL Unified API](https://api.tfl.gov.uk/) can be found here. It provides real-time and static data about London's public transport network, including: 

- Arrivals at stops and stations (buses, underground, overground, etc.)
- Line status (delays, closures, service updates)
- Vehicle locations for certain lines

Within the API, there is also other useful static data which provides information pertaining to stations, lines, routes and platforms (for example: names, geographic coordinates, etc..). I chose the TfL Unified API for this project, primarily because of the ability to track real-time insights - specifically, arrivals on a certain line live, which would enable me to build ETL pipelines reflecting current transit and mirror a real-world business use case. Furthermore, as it includes all lines, stops, and vehicles in London, this allows for both line-specific and network-wide analysis. The API itself is also frequently updated, which rendered it a suitable choice for this task.

## Scope

For this task, I made the decision to focus exclusively on the Central line of the London Underground - instead of importing data from every line. This was because limiting the data to a single line would allow for clearer analysis and more meaningful visualizations, without being overwhelmed by data from other lines. It also improves performance of the ETL pipeline and subsequent database operations, ensuring compliance with TfL API rate limits, and keeps the project manageable and easy to interpret. If I were to expand the project to multiple lines without comprising the pipeline's performance, I would consider techniques such as parallelization - specifically when making HTTP requests to API to speed up data extraction while respecting API rate limits. I would implement batch requests (fetch arrivals for a subset of stops or lines at a time, rather than all at once, to avoid overwhelming the API and my pipeline).


