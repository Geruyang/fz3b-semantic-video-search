package cnn_axi_pkg;
  typedef struct packed {
    logic arvalid;
    logic [63:0] araddr;
    logic [7:0] arlen;
    logic [2:0] arsize;
    logic [1:0] arburst;
    logic arlock;
    logic [3:0] arcache;
    logic [2:0] arprot;
    logic [3:0] arqos;
    logic arid;
    logic rready;
  } read_m2s_t;
  typedef struct packed {
    logic arready;
    logic rvalid;
    logic [127:0] rdata;
    logic [1:0] rresp;
    logic rlast;
    logic rid;
  } read_s2m_t;
  typedef struct packed {
    logic awvalid;
    logic [63:0] awaddr;
    logic [7:0] awlen;
    logic [2:0] awsize;
    logic [1:0] awburst;
    logic awlock;
    logic [3:0] awcache;
    logic [2:0] awprot;
    logic [3:0] awqos;
    logic awid;
    logic wvalid;
    logic [127:0] wdata;
    logic [15:0] wstrb;
    logic wlast;
    logic bready;
  } write_m2s_t;
  typedef struct packed {
    logic awready;
    logic wready;
    logic bvalid;
    logic [1:0] bresp;
    logic bid;
  } write_s2m_t;
endpackage
