from kubernetes import client, config, watch
import asyncio
from aiohttp.web import Application, WebSocketResponse, run_app, Response
from functools import partial
import json
import cachetools
import sys
import os
import dateutil.parser as dp
import datetime

EVENT_TTL = 600  # Expire events after 5 minutes


def flatten(y):
    out = {}

    def _flatten_inner(x, name=''):
        if type(x) is dict:
            for a in x:
                _flatten_inner(x[a], name + a + '_')
        elif type(x) is list:
            i = 0
            for a in x:
                _flatten_inner(a, name + str(i) + '_')
                i += 1
        else:
            out[name[:-1]] = x

    _flatten_inner(y)
    return out


async def metrics_handler(request, event_obj):
    header = "# TYPE kubernetes_events counter"
    metrics = "\n".join(
        'kubernetes_events{{{}}} {} {}'.format(",".join(['{}={}'.format(label, json.dumps(str(value))) for label, value in flatten(event).items()]), event['count'], int((dp.parse(event['lastTimestamp']).replace(tzinfo=datetime.timezone.utc) - datetime.datetime(1970, 1, 1).replace(tzinfo=datetime.timezone.utc)).total_seconds() * 1000))
        for event in event_obj.values()
    )
    return Response(text="\n".join([header, metrics, ""]))


async def watch_events_wrapper(event_obj, loop):
    try:
        await watch_events(event_obj)
    except Exception as e:
        current_count = 1 if 'k8s-event-metrics' not in event_obj else (event_obj['k8s-event-metrics']["count"] + 1)
        event_obj['k8s-event-metrics'] = {"message": str(e), "type": "Error", "reason": "Exception in k8s-event-metrics server", "count": current_count, "lastTimestamp": datetime.datetime.now().isoformat()}
    await asyncio.sleep(10)
    asyncio.ensure_future(watch_events_wrapper(event_obj, loop=loop), loop=loop)

async def watch_events(event_obj):
    config.load_kube_config()
    v1 = client.CoreV1Api()
    w = watch.Watch()
    gen = w.stream(v1.list_event_for_all_namespaces, _request_timeout=10)
    while True:
        event = await loop.run_in_executor(None, partial(next, gen))
        event_object = event['object']
        event_obj[event_object.involved_object.name] = event['raw_object']
        print(event['raw_object'])


async def start_background_tasks(app, event_obj):
    asyncio.ensure_future(watch_events_wrapper(event_obj, loop=app.loop), loop=app.loop)


async def init(loop):
    event_obj = cachetools.TTLCache(sys.maxsize, EVENT_TTL)
    app = Application()
    app.router.add_get('/metrics', partial(metrics_handler, event_obj=event_obj))
    app.on_startup.append(partial(start_background_tasks, event_obj=event_obj))
    return app


loop = asyncio.get_event_loop()
app = loop.run_until_complete(init(loop))
run_app(app, host='0.0.0.0', port=int(os.environ.get("PORT", "8080")))
