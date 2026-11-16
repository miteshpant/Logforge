# MinIO, built from the official source.
#
# The upstream `minio/minio` image was removed from Docker Hub, so the pinned
# tag in compose.yml stopped resolving and `./deploy.sh` failed on every fresh
# machine. This builds the same server from github.com/minio/minio, pinned to an
# exact module version so builds are reproducible.
#
# To upgrade: pick a newer version from
#   https://proxy.golang.org/github.com/minio/minio/@v/list   (or @latest)
# and update MINIO_VERSION (and GO_VERSION if the module's go.mod requires it).

ARG GO_VERSION=1.24
FROM golang:${GO_VERSION}-alpine AS build

ARG MINIO_VERSION=v0.0.0-20260212201848-7aac2a2c5b7c
# Override these behind a corporate module mirror. Checksum verification stays
# on by default; GOSUMDB can point at the same sumdb via another URL, e.g.
#   --build-arg GOSUMDB="sum.golang.org https://proxy.golang.org/sumdb/sum.golang.org"
ARG GOPROXY=https://proxy.golang.org,direct
ARG GOSUMDB=sum.golang.org
ENV CGO_ENABLED=0 \
    GOTOOLCHAIN=auto \
    GOPROXY=${GOPROXY} \
    GOSUMDB=${GOSUMDB}
RUN go install -trimpath -ldflags "-s -w" github.com/minio/minio@${MINIO_VERSION}

# Plain Alpine: no packages to install. The compose healthcheck uses busybox
# `wget`, which Alpine ships, so the runtime needs nothing beyond the binary.
FROM alpine:3.20
COPY --from=build /go/bin/minio /usr/bin/minio
EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["/usr/bin/minio"]
CMD ["server", "/data", "--console-address", ":9001"]
