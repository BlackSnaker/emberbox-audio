// SPDX-License-Identifier: MIT
// Licensed CDM API -> in-memory CENC/CBCS samples. No key export API.
#include "content_decryption_module.h"
#include <dlfcn.h>
#include <chrono>
#include <thread>
#include <vector>
#include <string>
#include <algorithm>
using Cdm=cdm::ContentDecryptionModule_11;
class Buffer final:public cdm::Buffer {
 std::vector<uint8_t> bytes;uint32_t size=0;
 public:explicit Buffer(uint32_t n):bytes(n){}void Destroy()override{delete this;}
 uint32_t Capacity()const override{return bytes.size();}uint8_t* Data()override{return bytes.data();}
 void SetSize(uint32_t n)override{if(n<=bytes.size())size=n;}uint32_t Size()const override{return size;}
};
class Host final:public cdm::Host_11 {
 public:Cdm* cdm=nullptr;bool called=false,initialized=false;size_t messages=0;size_t rejected=0;uint32_t lastException=0;std::string session;std::vector<uint8_t> message;size_t usable=0;std::vector<std::vector<uint8_t>> usableIds;
 struct Timer{std::chrono::steady_clock::time_point due;void* context;};std::vector<Timer> timers;
 cdm::Buffer* Allocate(uint32_t n)override{return n<=64*1024*1024?new Buffer(n):nullptr;}
 void SetTimer(int64_t ms,void* context)override{if(timers.size()<64)timers.push_back({std::chrono::steady_clock::now()+std::chrono::milliseconds(std::clamp<int64_t>(ms,0,60000)),context});}
 cdm::Time GetCurrentWallTime()override{return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();}
 void OnInitialized(bool ok)override{called=true;initialized=ok;}
 void OnResolveKeyStatusPromise(uint32_t,cdm::KeyStatus)override{}
 void OnResolveNewSessionPromise(uint32_t,const char* id,uint32_t n)override{if(n<=512)session.assign(id,n);}
 void OnResolvePromise(uint32_t)override{}
 void OnRejectPromise(uint32_t,cdm::Exception exception,uint32_t,const char*,uint32_t)override{rejected++;lastException=uint32_t(exception)+1;}
 void OnSessionMessage(const char*,uint32_t,cdm::MessageType type,const char* p,uint32_t n)override{messages++;if(type==cdm::kLicenseRequest&&n<=128*1024)message.assign(p,p+n);}
 void OnSessionKeysChange(const char*,uint32_t,bool,const cdm::KeyInformation* keys,uint32_t count)override{usable=0;usableIds.clear();for(uint32_t i=0;i<count;i++)if(keys[i].status==cdm::kUsable){usable++;if(keys[i].key_id_size<=128)usableIds.emplace_back(keys[i].key_id,keys[i].key_id+keys[i].key_id_size);}}
 void OnExpirationChange(const char*,uint32_t,cdm::Time)override{}
 void OnSessionClosed(const char*,uint32_t)override{}
 void SendPlatformChallenge(const char*,uint32_t,const char*,uint32_t)override{if(cdm)cdm->OnPlatformChallengeResponse({});}
 void EnableOutputProtection(uint32_t)override{}
 void QueryOutputProtectionStatus()override{if(cdm)cdm->OnQueryOutputProtectionStatus(cdm::kQueryFailed,0,0);}
 void OnDeferredInitializationDone(cdm::StreamType,cdm::Status)override{}
 cdm::FileIO* CreateFileIO(cdm::FileIOClient*)override{return nullptr;}
 void RequestStorageId(uint32_t version)override{if(cdm)cdm->OnStorageId(version,nullptr,0);}
 void ReportMetrics(cdm::MetricName,uint64_t)override{}
 void tick(){auto now=std::chrono::steady_clock::now();auto pending=std::move(timers);timers.clear();for(auto t:pending){if(t.due<=now)cdm->TimerExpired(t.context);else timers.push_back(t);}}
};
void* getHost(int version,void* user){return version==11?static_cast<cdm::Host_11*>(static_cast<Host*>(user)):nullptr;}
struct Instance {void* library=nullptr;Host host;void(*deinit)()=nullptr;};
extern "C" {
void* ember_cdm_create(const char* file){
 auto* p=new Instance;p->library=dlopen(file,RTLD_NOW|RTLD_LOCAL);if(!p->library){delete p;return nullptr;}
 auto init=reinterpret_cast<void(*)()>(dlsym(p->library,"InitializeCdmModule_4"));
 p->deinit=reinterpret_cast<void(*)()>(dlsym(p->library,"DeinitializeCdmModule"));
 auto create=reinterpret_cast<void*(*)(int,const char*,uint32_t,GetCdmHostFunc,void*)>(dlsym(p->library,"CreateCdmInstance"));
 if(!init||!create||!p->deinit){dlclose(p->library);delete p;return nullptr;}init();
 p->host.cdm=static_cast<Cdm*>(create(11,"com.widevine.alpha",18,getHost,&p->host));
 if(!p->host.cdm){p->deinit();dlclose(p->library);delete p;return nullptr;}
 p->host.cdm->Initialize(false,false,false);return p;
}
int ember_cdm_state(Instance* p){p->host.tick();return p->host.initialized?1:p->host.called?-1:0;}
void ember_cdm_destroy(Instance* p){if(!p)return;p->host.cdm->Destroy();p->deinit();dlclose(p->library);delete p;}
int ember_cdm_certificate(Instance*p,const uint8_t*data,uint32_t n){if(!data||n>131072)return -1;p->host.cdm->SetServerCertificate(1,data,n);p->host.tick();return p->host.rejected?-1:0;}
int ember_cdm_generate(Instance*p,const uint8_t*data,uint32_t n){if(!data||n>131072)return -1;p->host.message.clear();p->host.session.clear();p->host.cdm->CreateSessionAndGenerateRequest(2,cdm::kTemporary,cdm::kCenc,data,n);p->host.tick();return p->host.rejected?-1:0;}
int ember_cdm_message(Instance*p,uint8_t*data,uint32_t cap){p->host.tick();auto n=p->host.message.size();if(!n||cap<n)return 0;std::copy(p->host.message.begin(),p->host.message.end(),data);return n;}
int ember_cdm_update(Instance*p,const uint8_t*data,uint32_t n){if(p->host.session.empty()||!data||n>131072)return -1;p->host.cdm->UpdateSession(3,p->host.session.data(),p->host.session.size(),data,n);p->host.tick();return p->host.rejected?-1:0;}
int ember_cdm_usable(Instance*p){p->host.tick();return p->host.usable;}
int ember_cdm_exception(Instance*p){return p->host.lastException;}
}
class Decrypted final:public cdm::DecryptedBlock{
 cdm::Buffer* data=nullptr;int64_t timestamp=0;
 public:~Decrypted(){if(data)data->Destroy();}
 void SetDecryptedBuffer(cdm::Buffer*b)override{if(data)data->Destroy();data=b;}
 cdm::Buffer* DecryptedBuffer()override{return data;}
 void SetTimestamp(int64_t t)override{timestamp=t;}int64_t Timestamp()const override{return timestamp;}
};

extern "C" int ember_cdm_packet(Instance*p,const uint8_t*data,uint32_t size,const uint8_t*kid,const uint8_t*iv,
 const cdm::SubsampleEntry*subs,uint32_t count,uint32_t scheme,uint32_t crypt,uint32_t skip,void(*deliver)(const uint8_t*,uint32_t)){
 if(!p||!data||!kid||!iv||!deliver||size>1048576||count>1024||scheme<1||scheme>2||crypt>15||skip>15)return -1;
 uint64_t total=0;for(uint32_t i=0;i<count;i++)total+=uint64_t(subs[i].clear_bytes)+subs[i].cipher_bytes;
 if(count&&total!=size)return -1;
 cdm::InputBuffer_2 input{};input.data=data;input.data_size=size;input.key_id=kid;input.key_id_size=16;input.iv=iv;input.iv_size=16;
 input.subsamples=subs;input.num_subsamples=count;input.encryption_scheme=scheme==2?cdm::EncryptionScheme::kCbcs:cdm::EncryptionScheme::kCenc;input.pattern={crypt,skip};
 Decrypted out;p->host.tick();auto status=p->host.cdm->Decrypt(input,&out);
 if(status!=cdm::kSuccess)return -100-int(status);auto*buffer=out.DecryptedBuffer();if(!buffer||buffer->Size()!=size)return -9;
 deliver(buffer->Data(),buffer->Size());return 1;
}
