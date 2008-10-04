#!/usr/bin/env python
#
##
# Copyright (c) 2006-2007 Apple Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
##
#
# A thread pool based function executor. This class takes a function as an argument
# and multiple sets of arguments to the function, and it executes the function with
# each argument set in a thread in parallel. The total number of threads is limited by
# the thread pool and a queue is used to hold pending function executions.
#
# Code is copied from O'Reilly Python Cookbook Recipe 9.3.
#
from random import randrange

import time
import Queue
import threading

class MultiThread(object):

    def __init__(self, function, argsVector, maxThreads=5, queue_results=False, sleep=0.0):
        self._function = function
        self._lock = threading.Lock( )
        self._nextArgs = iter(argsVector).next
        self._threadPool = [ threading.Thread(target=self._doSome, args=(i,))
                             for i in range(maxThreads) ]
        if queue_results:
            self._queue = Queue.Queue( )
        else:
            self._queue = None
            
        self.sleep = sleep

    def _doSome(self, ctr):
        while True:
            
            self._lock.acquire( )
            try:
                try:
                    args = self._nextArgs( )
                except StopIteration:
                    break
            finally:
                self._lock.release( )
            # Insert user provided delay in here
            if self.sleep != 0.0:
                sleeper = randrange(0, 100)/100.0 * self.sleep
                #print sleeper
                c = time.clock()
                #print c
                while time.clock() - c < sleeper:
                    time.sleep(0)    # necessary to give other threads a chance to run
                    j = 0
                    for i in range(100):
                        j += i
                #time.sleep(sleeper)
            else:
                sleeper = 0.0

            try:
                #print "Thread: %d, %f" % (ctr, sleeper)
                result = self._function(args)
                if self._queue is not None:
                    self._queue.put((args, result))
            except Exception, e:
                print "Exception: %s" % e

    def get(self, *a, **kw):
        if self._queue is not None:
            return self._queue.get(*a, **kw)
        else:
            raise ValueError, 'Not queueing results'

    def start(self):
        for thread in self._threadPool:
            time.sleep(0)    # necessary to give other threads a chance to run
            thread.start( )

    def join(self, timeout=None):
        for thread in self._threadPool:
            thread.join(timeout)

