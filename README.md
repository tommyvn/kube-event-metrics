# [kube-event-metrics](https://github.com/tommyvn/kube-event-metrics)

Expose `kubernetes_event` metrics on `/metrics` for Prometheus

Really this should be implemented in https://github.com/kubernetes/kube-state-metrics but until I have time to create a PR against it this will do...

## Usage

`kubectl apply -f k8s/kube-event-metrics.yaml`

## Known issues

There are exactly 0 unit tests because the right place to do this and the place to do this right is https://github.com/kubernetes/kube-state-metrics so I didn't bother.
