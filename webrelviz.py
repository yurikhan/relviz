#!/usr/bin/python3

import asyncio
from asyncio.subprocess import PIPE
import os
import sys

from aiohttp import web

import fact_parser
import relviz

async def form(request):
    with open(os.path.join(os.path.dirname(sys.argv[0]), 'index.html')) as f:
        return web.Response(text=f.read(),
                            content_type='text/html',
                            charset='utf-8')

async def static(request):
    with open(os.path.join(os.path.dirname(sys.argv[0]),
                           'assets',
                           request.match_info['filename'])) as f:
        return web.Response(text=f.read(),
                            content_type='text/html',
                            charset='utf-8')

PROCESSORS = {'dot': '/usr/bin/dot',
              'fdp': '/usr/bin/fdp'}

async def render(request):
    post_data = await request.post()
    try:
        processor = PROCESSORS[post_data['processor']]
    except KeyError:
        return web.Response(text='Unsupported processor: %s'
                            % post_data['processor'],
                            status=501)
    try:
        style_facts = fact_parser.parse(relviz.load_default_style())
    except Exception as e:
        return web.Response(text=str(e), status=500)
    try:
        facts = fact_parser.parse(post_data['facts'] + '\n')
        style_facts.extend(facts)
        g = relviz.to_graphviz(facts, style_facts)
        dot = await asyncio.create_subprocess_exec(
            processor, '-Tsvg',
            stdin=PIPE, stdout=PIPE, stderr=PIPE)
        output, errors = await dot.communicate(g.to_string().encode('utf-8'))
        if dot.returncode == 0:
            return web.Response(text=output.decode('utf-8'),
                                content_type='image/svg+xml')
        return web.Response(text=errors.decode('utf-8'), status=500)
    except (fact_parser.ParseException, relviz.GraphError) as e:
        return web.Response(text=str(e), status=400)
    except Exception as e:
        return web.Response(text=str(e), status=500)

def main():
    app = web.Application()
    app.router.add_route('GET', '/', form)
    app.router.add_static('/assets',
                          os.path.join(os.path.dirname(sys.argv[0]), 'assets'))
    app.router.add_route('POST', '/render', render)

    loop = asyncio.get_event_loop()
    handler = app.make_handler()
    f = loop.create_server(handler, '0.0.0.0', 8080)
    server = loop.run_until_complete(f)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.run_until_complete(handler.finish_connections(1.0))
        loop.run_until_complete(app.finish())
    loop.close()

if __name__ == '__main__':
    main()
