console = { log: function(x) { call_python("log", x); } }

// wraps a handle
function Node(handle) {
    this.handle = handle;
}

// dom api
document = {
    querySelectorAll: function (s) {
        var handles = call_python("querySelectorAll", s);
        return handles.map(function(h){
            return new Node(h)
        });
    }
}