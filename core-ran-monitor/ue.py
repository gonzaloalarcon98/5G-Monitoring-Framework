class UE:
    def __init__(self, ran_ue, amf_ue, imsi):
        self.ran_ue = ran_ue
        self.amf_ue = amf_ue
        self.imsi = imsi

    def __repr__(self):
        return f"RAN_UE: {self.ran_ue} - AMF_UE: {self.amf_ue} - IMSI: {self.imsi}"

    def __str__(self):
        return f"RAN_UE: {self.ran_ue} - AMF_UE: {self.amf_ue} - IMSI: {self.imsi}"

    def __eq__(self, other):
        if not isinstance(other, UE):
            return NotImplemented
        return (
            ((0 if self.ran_ue == None else int(self.ran_ue)) == (1 if other.ran_ue == None else int(other.ran_ue)) and
            (0 if self.amf_ue == None else int(self.amf_ue)) == (1 if other.amf_ue == None else int(other.amf_ue))) or
            ((None if self.imsi == None else int(self.imsi)) == (
                None if other.imsi == None else int(other.imsi)))
        )
