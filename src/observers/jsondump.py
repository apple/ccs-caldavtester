##
# Copyright (c) 2014-2016 Apple Inc. All rights reserved.
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

from src.observers.base import BaseResultsObserver
import json
import time


class Observer(BaseResultsObserver):
    """
    A results observer that prints results to standard output.
    """

    def __init__(self, manager):
        super(Observer, self).__init__(manager)
        self.currentProtocol = []

    def updateCalls(self):
        super(Observer, self).updateCalls()
        self._calls.update({
            "finish": self.finish,
            "protocol": self.protocol,
            "testSuite": self.testSuite,
            "testResult": self.testResult,
        })

    def protocol(self, result):
        self.currentProtocol.append(result)

    def testResult(self, result):
        result["time"] = time.time()
        if self.currentProtocol:
            result["protocol"] = self.currentProtocol
            self.currentProtocol = []

    def testSuite(self, result):
        result["time"] = time.time()

    def finish(self):
        print(json.dumps(self.manager.results))
