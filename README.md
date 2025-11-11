# Movie Normalizer

This project is for movies to optimize the volume, espeically of dialogues, for stereo.
The tool is deployed as docker container.
The containers is to be called with:

```sh
docker run --rm -v "$DATA_DIR":/data movie-normalizer "/data/$INPUT" "/data/$OUTPUT"
```

See `executer.sh` for a system deployable executable.
