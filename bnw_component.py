# -*- coding: utf8 -*-
"""
 Example component service.
 
"""
import time
from twisted.words.protocols.jabber import jid, xmlstream
from twisted.application import internet, service
from twisted.internet import interfaces, defer, reactor
from twisted.python import log
from twisted.words.xish import domish


from twisted.words.protocols.jabber.ijabber import IService
from twisted.words.protocols.jabber import component

from zope.interface import Interface, implements

from twisted.web.client import getPage
from twisted import web

from twisted.python.util import println
from twisted.web import resource, server, static, xmlrpc

import twisted.internet.error as error

from twisted.internet.threads import deferToThread
import stupid_handler
#.ConnectionRefusedError
#import simplejson
#import cPickle as pickle

#import command_parsers
#import commands
import bnw_xmpp.base
import bnw_core.bnw_objects as objs

PRESENCE = '/presence' # this is an global xpath query to use in an observer
MESSAGE  = '/message'  # message xpath 
IQ       = '/iq'       # iq xpath

def create_reply(elem):
    """ switch the 'to' and 'from' attributes to reply to this element """
    # NOTE - see domish.Element class to view more methods 
    frm = elem['from']
    elem['from'] = elem['to']
    elem['to']   = frm
    return elem

class LogService(component.Service):
    """
    A service to log incoming and outgoing xml to and from our XMPP component.

    """
    
    def transportConnected(self, xmlstream):
        xmlstream.rawDataInFn = self.rawDataIn
        xmlstream.rawDataOutFn = self.rawDataOut

    def rawDataIn(self, buf):
        log.msg("%s - RECV: %s" % (str(time.time()), unicode(buf, 'utf-8').encode('ascii', 'replace')))

    def rawDataOut(self, buf):
        log.msg("%s - SEND: %s" % (str(time.time()), unicode(buf, 'utf-8').encode('ascii', 'replace')))


#class MessageSender(xmlrpc.XMLRPC):
#    """An example object to be published.
#    
#    Has five methods accessable by XML-RPC, 'echo', 'hello', 'defer',
#    'defer_fail' and 'fail.
#    """
#    
#    def xmlrpc_send(self, jid, src, msg):
#        """Send to jid."""
#        return self.service.send_plain(jid, src, msg)
    

class BnwService(component.Service):
    """
    Example XMPP component service using twisted words.

    Basic Echo - We return the xml that is sent us.
    
    """
    implements(IService)

        
    def componentConnected(self, xmlstream):
        """
        This method is called when the componentConnected event gets called.
        That event gets called when we have connected and authenticated with the XMPP server.
        """
        
        self.jabberId = xmlstream.authenticator.otherHost
        self.xmlstream = xmlstream # set the xmlstream so we can reuse it
        bnw_xmpp.base.service=self # bakabakabaka
        
        xmlstream.addObserver(PRESENCE, self.onPresence, 1)
        xmlstream.addObserver(IQ, self.onIq, 1)
        xmlstream.addObserver(MESSAGE, self.onMessage, 1)

    def proceedWithMessage(self,data,msg):
        import pprint
        #log.msg(pprint.pformat(data))
        try:
            user=data['rows'][0]['value']
        except (IndexError, KeyError): #this SUCKS
            #raise
            user=None
        command_parsers.handleCommand(user,self,msg)

    def send_plain(self, jid, src, content):
        msg = domish.Element((None, "message"))
        msg["to"] = jid
        msg["from"] = self.jabberId if (src is None) else src
        msg["type"] = 'chat'
        msg.addElement("body", content=content)
        msg.addChild(domish.Element(('http://jabber.org/protocol/chatstates','active')))
        self.xmlstream.send(msg)

    def callbackMessage(self,result,jid,stime,src,body):
        etime=time.time()-stime
        println('result:',result)
        self.send_plain(jid,src,str(result))
        t=objs.Timing({'date': stime, 'time': etime, 'command': unicode(body),'jid': jid})
        t.save().addCallback(lambda x: None)
        log.msg("%s - PROCESSING TIME (from %s): %f" % (str(time.time()), jid, etime))
        if jid.startswith('stiletto@stiletto.name'):
            self.send_plain(jid,src,'I did it in %f seconds.' % (etime,) )

    def errbackMessage(self,result,jid,src):
        #println('error:',result)
        if result.type in (error.ConnectionRefusedError,):
            self.send_plain(jid,src,"Oops, our backend is down!\n")
        elif result.type==web.error.Error:
            self.send_plain(jid,src,"Aw, stupid backend has encountered an error but we even can't tell you /what/ error because it died too fast.")
        else:
            self.send_plain(jid,src,'error: '+str(result))
        
    def onMessage(self, msg):
        """
        Act on the message stanza that has just been received.

        """
        try:
            if msg['type']!='chat' or str(msg.body) in ('','None'):
                return
        except KeyError: # somebody plz kick ma ass 4 dat
            return
        stime=time.time()
        #else:
        #    println(msg.body)
        cmsg = domish.Element((None, "message"))
        cmsg["to"] = msg['from']
        cmsg["from"] = msg['to']
        cmsg["type"] = 'chat'
        cmsg.addChild(domish.Element(('http://jabber.org/protocol/chatstates','composing')))
        self.xmlstream.send(cmsg)
        
        gp=stupid_handler.idiotic(msg)
        #self.send_plain(msg['from'],'processing...')
        #gp=getPage('http://localhost:8080/xmpp_rpc/message', method='POST',postdata=msg.toXml().encode('utf-8','replace'),headers={'Content-Type':'application/octet-stream'})
        gp.addCallback(self.callbackMessage,jid=msg['from'],stime=stime,src=msg['to'],body=msg.body)
        gp.addErrback(self.errbackMessage,jid=msg['from'],src=msg['to'])
        
        
    def onIq(self, iq):
        """
        Act on the iq stanza that has just been received.

        """

        #iq = create_reply(iq)
        #self.xmlstream.send(iq)
        pass
            
    def onPresence(self, prs):
        """
        Act on the presence stanza that has just been received.

        """
        prs = create_reply(prs)
        self.xmlstream.send(prs)

    def getResource(self):
        r = resource.Resource()
        r.getChild = (lambda path, request:
                      static.Data('<h1>fuck</h1>',
                      'text/html'))
        x = xmlrpc.XMLRPC()
        x.xmlrpc_send_plain = lambda jid,src,msg: str(self.send_plain(jid,src,msg))
        r.putChild('RPC2', x)
        return r
