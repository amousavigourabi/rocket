# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: protos/packet.proto
# Protobuf Python Version: 5.26.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x13protos/packet.proto\x12\x06packet\":\n\x06Packet\x12\x0c\n\x04\x64\x61ta\x18\x01 \x01(\x0c\x12\x11\n\tfrom_port\x18\x02 \x01(\r\x12\x0f\n\x07to_port\x18\x03 \x01(\r\">\n\tPacketAck\x12\x0c\n\x04\x64\x61ta\x18\x01 \x01(\x0c\x12\x0e\n\x06\x61\x63tion\x18\x02 \x01(\r\x12\x13\n\x0bsend_amount\x18\x03 \x01(\r\"\xe7\x01\n\x11ValidatorNodeInfo\x12\x11\n\tpeer_port\x18\x01 \x01(\r\x12\x16\n\x0ews_public_port\x18\x02 \x01(\r\x12\x15\n\rws_admin_port\x18\x03 \x01(\r\x12\x10\n\x08rpc_port\x18\x04 \x01(\r\x12\x0e\n\x06status\x18\x05 \x01(\t\x12\x16\n\x0evalidation_key\x18\x06 \x01(\t\x12\x1e\n\x16validation_private_key\x18\x07 \x01(\t\x12\x1d\n\x15validation_public_key\x18\x08 \x01(\t\x12\x17\n\x0fvalidation_seed\x18\t \x01(\t\"&\n\x14ValidatorNodeInfoAck\x12\x0e\n\x06status\x18\x01 \x01(\t\"\x0b\n\tGetConfig\"\x1a\n\tPartition\x12\r\n\x05nodes\x18\x01 \x03(\r\"\xd8\x01\n\x06\x43onfig\x12\x16\n\x0e\x62\x61se_port_peer\x18\x01 \x01(\r\x12\x14\n\x0c\x62\x61se_port_ws\x18\x02 \x01(\r\x12\x1a\n\x12\x62\x61se_port_ws_admin\x18\x03 \x01(\r\x12\x15\n\rbase_port_rpc\x18\x04 \x01(\r\x12\x17\n\x0fnumber_of_nodes\x18\x05 \x01(\r\x12)\n\x0enet_partitions\x18\x06 \x03(\x0b\x32\x11.packet.Partition\x12)\n\x0eunl_partitions\x18\x07 \x03(\x0b\x32\x11.packet.Partition2\xc9\x01\n\rPacketService\x12\x30\n\x0bsend_packet\x12\x0e.packet.Packet\x1a\x11.packet.PacketAck\x12U\n\x18send_validator_node_info\x12\x19.packet.ValidatorNodeInfo\x1a\x1c.packet.ValidatorNodeInfoAck(\x01\x12/\n\nget_config\x12\x11.packet.GetConfig\x1a\x0e.packet.Configb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'protos.packet_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_PACKET']._serialized_start=31
  _globals['_PACKET']._serialized_end=89
  _globals['_PACKETACK']._serialized_start=91
  _globals['_PACKETACK']._serialized_end=153
  _globals['_VALIDATORNODEINFO']._serialized_start=156
  _globals['_VALIDATORNODEINFO']._serialized_end=387
  _globals['_VALIDATORNODEINFOACK']._serialized_start=389
  _globals['_VALIDATORNODEINFOACK']._serialized_end=427
  _globals['_GETCONFIG']._serialized_start=429
  _globals['_GETCONFIG']._serialized_end=440
  _globals['_PARTITION']._serialized_start=442
  _globals['_PARTITION']._serialized_end=468
  _globals['_CONFIG']._serialized_start=471
  _globals['_CONFIG']._serialized_end=687
  _globals['_PACKETSERVICE']._serialized_start=690
  _globals['_PACKETSERVICE']._serialized_end=891
# @@protoc_insertion_point(module_scope)
