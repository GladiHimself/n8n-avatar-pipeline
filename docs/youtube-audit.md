# YouTube API audit — prepared answers

Project name:   avatar-content-pipeline
Project ID:     avatar-content-pipeline
Project number: 515333513515
OAuth client:   n8n-local
Channel:        https://www.youtube.com/@n8nProject-f4t
Scopes:         youtube.upload, youtube.force-ssl
Form:           support.google.com/youtube/contact/yt_api_form
Status:         NOT SUBMITTED — submit after the first successful upload (Day 13)

## What the application does
An internal content pipeline for a single YouTube channel owned by the
account holder. A topic is entered by the channel owner; the system
generates a script, synthesises narration and an AI presenter video,
edits it, and sends the finished video to the owner for review.

## Human review
No video is uploaded without explicit human approval. The owner receives
each finished video and must approve it before the upload step runs.

## Synthetic content
Every upload sets the altered/synthetic content disclosure flag. The
videos are AI-generated presenter footage and are declared as such on
every upload, without exception.

## Scope of use
Uploads to one channel only, owned by the party operating the pipeline.
No third-party user data is accessed. No public-facing product. Expected
volume is well within the default 10,000 unit/day quota (~1,600 units
per upload).

## API methods used
videos.insert, thumbnails.set, videos.update, and videos.list for
post-publish statistics on the channel's own videos.