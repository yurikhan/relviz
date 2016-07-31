#!/usr/bin/python3

import argparse
import asyncio
from asyncio.subprocess import PIPE
import logging
import logging.handlers
import os
import sys
import traceback

from aiohttp import web
import daemon
from lockfile.pidlockfile import PIDLockFile
from setproctitle import setproctitle

import fact_parser
import relviz

_self_path = None


async def form(request):
    with open(os.path.join(_self_path, 'index.html')) as f:
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
        return web.Response(text=''.join(traceback.format_exc()), status=400)
    except Exception as e:
        return web.Response(text=''.join(traceback.format_exc()), status=500)


def daemon_main():
    app = web.Application()
    app.router.add_route('GET', '/', form)
    app.router.add_static('/assets', os.path.join(_self_path, 'assets'))
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


def main():
    setproctitle('webrelviz')
    parser = argparse.ArgumentParser('Relviz web interface daemon')
    parser.add_argument('-D', '--no-daemon', action='store_true',
                        help='Do not daemonize')
    parser.add_argument('--pid-file', default='/var/run/webrelviz.pid',
                        help='Path to PID file')
    parser.add_argument('-v', '--verbose', default=0, action='count',
                        help='Enable debug logging. Repeat for more')

    args = parser.parse_args()

    if args.no_daemon:
        logging.basicConfig(stream=sys.stderr,
                            format='%(message)s')
        logging.getLogger(__name__).setLevel(logging.DEBUG if args.verbose
                                             else logging.INFO)
        logging.getLogger('relviz').setLevel(logging.DEBUG if args.verbose >= 2
                                             else logging.INFO)
        daemon_main()
    else:
        logging.basicConfig(
            handlers=[logging.handlers.SysLogHandler(address='/dev/log')],
            format='webrelviz[%(process)d]: <%(levelname)s> %(message)s')
        logging.getLogger(__name__).setLevel(logging.DEBUG if args.verbose
                                             else logging.INFO)
        logging.getLogger('relviz').setLevel(logging.DEBUG if args.verbose >= 2
                                             else logging.INFO)

        try:
            pidfile = PIDLockFile(args.pid_file)
            # Initialize `_self_path` before daemonizing, as it becomes
            # near-impossible afterwards
            global _self_path
            _self_path = os.path.dirname(os.path.realpath(__file__))
            logging.getLogger(__name__).debug('before daemonization')
            with daemon.DaemonContext(pidfile=pidfile):
                logging.getLogger(__name__).debug('after daemonization')
                daemon_main()
        except Exception:
            etype, e, tb = sys.exc_info()
            try:
                for line in traceback.format_exception_only(etype, e):
                    logging.getLogger(__name__).error(line)
                for line in ''.join(traceback.format_tb(tb)).split('\n'):
                    logging.getLogger(__name__).debug(line)
            except Exception as ee:
                logging.getLogger(__name__).error(ee)


if __name__ == '__main__':
    main()
