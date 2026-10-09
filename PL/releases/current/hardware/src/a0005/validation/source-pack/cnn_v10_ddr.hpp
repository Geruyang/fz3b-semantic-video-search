#pragma once

#ifndef AP_INT_MAX_W
#define AP_INT_MAX_W 2048
#endif

#include <ap_int.h>
#include <hls_stream.h>
#include <hls_burst_maxi.h>

#ifndef __SYNTHESIS__
#include <cassert>
#endif

namespace cnn_v10 {

typedef ap_uint<128> DdrWord;

struct WriteCmd {
    ap_uint<32> offset;
    ap_uint<6> count;
    ap_uint<1> end;
    WriteCmd():offset(0),count(0),end(0) {}
    WriteCmd(ap_uint<32> at,ap_uint<6> words,ap_uint<1> stop=0)
        :offset(at),count(words),end(stop) {}
};

class DdrWriter {
public:
    DdrWriter(hls::stream<WriteCmd>& commands,hls::stream<DdrWord>& data,
              hls::stream<ap_uint<1> >& committed)
        :commands_(commands),data_(data),committed_(committed),offset_(0),
         count_(0),written_(0),finished_(0) {}
    void request(unsigned offset,unsigned count) {
#pragma HLS INLINE
#ifndef __SYNTHESIS__
        assert(!finished_ && count_==0 && count>=1 && count<=32);
#endif
        offset_=offset;count_=count;written_=0;
    }
    void write(const DdrWord& value) {
#pragma HLS INLINE
#ifndef __SYNTHESIS__
        assert(count_!=0 && written_<count_);
#endif
        data_.write(value);
        ++written_;
    }
    void commit() {
#pragma HLS INLINE off
#ifndef __SYNTHESIS__
        assert(count_!=0 && written_==count_);
#endif
        // Publish the command only after its complete burst is buffered. The
        // shared broker therefore never owns the AXI port while waiting for a
        // producer that may itself be downstream of the other write client.
        // A blocking write followed by a blocking acknowledgement read can
        // be co-scheduled into one HLS stage.  If the acknowledgement FIFO is
        // initially empty, that stage blocks the command write that would
        // create the acknowledgement (observed in HLS004 RTL).  Pump both
        // nonblocking interfaces so publishing is independent of ack state.
        const WriteCmd command(offset_,count_,0);
        ap_uint<1> published=0,acknowledged=0;
        while(!acknowledged) {
#pragma HLS PIPELINE II=1
            if(!published && commands_.write_nb(command)) published=1;
            ap_uint<1> token;
            if(published && committed_.read_nb(token)) {
#ifndef __SYNTHESIS__
                assert(token==1);
#endif
                acknowledged=1;
            }
        }
        count_=0;written_=0;
    }
    void finish() {
#pragma HLS INLINE
#ifndef __SYNTHESIS__
        assert(!finished_ && count_==0);
#endif
        commands_.write(WriteCmd(0,0,1));
        finished_=1;
    }
private:
    hls::stream<WriteCmd>& commands_;
    hls::stream<DdrWord>& data_;
    hls::stream<ap_uint<1> >& committed_;
    ap_uint<32> offset_;
    ap_uint<6> count_;
    ap_uint<6> written_;
    ap_uint<1> finished_;
};

namespace detail {
template<int N>
void write_commit(hls::stream<ap_uint<1> > (&committed)[N],int selected) {
#pragma HLS INLINE
    for(int i=0;i<N;++i) {
#pragma HLS UNROLL
        if(selected==i) committed[i].write(1);
    }
}
}

// One owner for an activation write bundle. Commands are atomic bursts, and
// completion is returned only after the AXI B response has been observed.
template<int N>
void write_broker(hls::burst_maxi<DdrWord> memory,
                  hls::stream<WriteCmd> (&commands)[N],
                  hls::stream<DdrWord> (&data)[N],
                  hls::stream<ap_uint<1> > (&committed)[N]) {
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=commands complete dim=1
#pragma HLS ARRAY_PARTITION variable=data complete dim=1
#pragma HLS ARRAY_PARTITION variable=committed complete dim=1
    WriteCmd pending[N];ap_uint<1> valid[N],ended[N];
#pragma HLS ARRAY_PARTITION variable=pending complete dim=1
#pragma HLS ARRAY_PARTITION variable=valid complete dim=1
#pragma HLS ARRAY_PARTITION variable=ended complete dim=1
    for(int i=0;i<N;++i) {
#pragma HLS UNROLL
        valid[i]=0;ended[i]=0;
    }
    unsigned rr=0,done=0;
    while(done!=unsigned(N)) {
        for(int i=0;i<N;++i) {
#pragma HLS UNROLL
            if(!ended[i]&&!valid[i]) {
                WriteCmd candidate;
                if(commands[i].read_nb(candidate)) {pending[i]=candidate;valid[i]=1;}
            }
        }
        int selected=-1;
        for(int distance=0;distance<N;++distance) {
#pragma HLS UNROLL
            unsigned ix=rr+unsigned(distance);if(ix>=unsigned(N)) ix-=unsigned(N);
            if(selected<0&&valid[ix]) selected=int(ix);
        }
        if(selected<0) continue;
        WriteCmd command=pending[selected];valid[selected]=0;
        rr=unsigned(selected+1);if(rr==unsigned(N)) rr=0;
        if(command.end) {ended[selected]=1;++done;continue;}
#ifndef __SYNTHESIS__
        assert(command.count>=1&&command.count<=32);
#endif
        memory.write_request(unsigned(command.offset),unsigned(command.count));
        for(unsigned word=0;word<unsigned(command.count);++word) {
#pragma HLS PIPELINE II=1
            DdrWord value=0;
            for(int i=0;i<N;++i) {
#pragma HLS UNROLL
                if(selected==i) value=data[i].read();
            }
            memory.write(value);
        }
        memory.write_response();
        detail::write_commit<N>(committed,selected);
    }
}

} // namespace cnn_v10
