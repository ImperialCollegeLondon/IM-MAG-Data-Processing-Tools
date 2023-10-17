#!/bin/bash

sciFolder=$(wslpath "C:\Users\acrabtre\Imperial College London\IMAP - PH - Documents\General\Documents\Test & Inspection Reports")

# ASW 1.x NORMAL files
find "$sciFolder" -name "normal*.csv" | while read line; do
    echo "Processing $line"
    mag check-gap "$line"
done

# ASW 1.x Burst Files
find "$sciFolder" -name "burst*.csv" | while read line; do
    echo "Processing $line"
    mag check-gap "$line"
done

# ASW3+ files
find "$sciFolder" -name "MAGScience*.csv" | while read line; do
    echo "Processing $line"
    mag check-gap "$line"
done

sciFolder=$(wslpath "C:\Users\acrabtre\Imperial College London\IMAP - PH - Documents\General\Science\SFT Science Data 22-85\FM")

# ASW 1.x NORMAL files
find "$sciFolder" -name "normal*.csv" | while read line; do
    echo "Processing $line"
    mag check-gap "$line"
done

# ASW 1.x Burst Files
find "$sciFolder" -name "burst*.csv" | while read line; do
    echo "Processing $line"
    mag check-gap "$line"
done

# ASW3+ files
find "$sciFolder" -name "MAGScience*.csv" | while read line; do
    echo "Processing $line"
    mag check-gap "$line"
done

sciFolder=$(wslpath "C:\Users\acrabtre\Imperial College London\IMAP - PH - Documents\General\Science\SFT Science Data 22-85\FM Prep with EM")

# ASW 1.x NORMAL files
find "$sciFolder" -name "normal*.csv" | while read line; do
    echo "Processing $line"
    mag check-gap "$line"
done

# ASW 1.x Burst Files
find "$sciFolder" -name "burst*.csv" | while read line; do
    echo "Processing $line"
    mag check-gap "$line"
done

# ASW3+ files
find "$sciFolder" -name "MAGScience*.csv" | while read line; do
    echo "Processing $line"
    mag check-gap "$line"
done