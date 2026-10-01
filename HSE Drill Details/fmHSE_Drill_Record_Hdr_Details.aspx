<%@ Page Language="C#" AutoEventWireup="true" CodeFile="fmHSE_Drill_Record_Hdr_Details.aspx.cs"
    Inherits="Quality_And_Safety_fmHSE_Drill_Record_Hdr_Details" %>

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Head1" runat="server">
    <title>HSE_Drill_Record_Hdr details</title>
   <link href="../../StyleSheet.css" type="text/css" rel="stylesheet" />
    <script type="text/javascript" language="javascript" src="../../Javascript/generic.js"> </script> 
    <script type="text/javascript" language="javascript" src="../../Javascript/Open_Search.js"> </script>
    <script type="text/javascript" language="javascript" src="../../Javascript/Open_ErrorWin.js"> </script>   
    <script type="text/javascript" language="javascript" src="../../JavaScript/jquery.min.js"></script>
    <script type="text/javascript" language="javascript" src="../../JavaScript/bootstrap.min.js"></script>
    <script type="text/javascript" language="javascript" src="../../JavaScript/CommonModal.js"></script>
    
    <link href="../../BootstrapStyleSheet.min.css" type="text/css" rel="stylesheet" />  
    <script type="text/javascript">

        // Initialize custom Dialog Box
        window.onload = function () {
           
        }



        function Change_Color(obj) {
            obj.style.color = 'black';
        }


        function validate(strFlag) {
            var msg = "";
            var strServerDt = '<%= Session["ServerDt"].ToString() %>';

            /// Set a value to indicate the control/event that causes a postback.
            SetPostbackFlag(strFlag);
            if (strFlag == "ADD") {
                /// Blocking ADD button when an existing record is selected.
                if (document.getElementById('<%=tbDrill_Record_Hdr_Id_Hidden.ClientID%>').value != "") {
                    ShowMessage(400, 75, 'You are currently in Update mode. A new record cannot be added in this mode.');
                    return false;
                }
            }
            if (strFlag == 'DELETE') {
                if (document.getElementById('<%=tbDrill_Record_Hdr_Id_Hidden.ClientID%>').value == "") {
                    ShowMessage(400, 75, 'Select record to Delete.');
                    return false;
                }
                else {
                    var chk_Delete_Status = confirm("Are you sure you want to Delete this Record ?");
                    if (chk_Delete_Status == true) {
                        return true;
                    }
                    else {
                        return false;
                    }
                }
            }


            if (msg == "") {
                return true;
            }
            else {
                ShowErrorWin1(msg);
                // alert("The following errors were encountered \n" + msg);
                return false;
            }
        }


        function Show_Main_Data() {
            SetPostbackFlag("SEARCH");
            Open_Search_Window('HSE_DRILL_RECORD_HDR', document.forms[0].name, 'tbDrill_Record_Hdr_Id_Hidden', 'tbRig_Name', '', '%', 'Y', 'Y', 'N');
            return;
        }

        function ShowRig() {
            SetPostbackFlag("RIG");
            Open_Search_Window('RIG', document.forms[0].name, 'tbRig_Id_Hidden', 'tbRig_Name', '', '%', 'N', 'Y', 'N');
            return;
        }


        function SetPostbackFlag(strFlag) {
            document.getElementById('<%=tbPostbackFlag_Hidden.ClientID%>').value = strFlag;
            return true;
        }
    </script>
 

</head>
<body class="body" onkeydown="if (event.keyCode==13) {event.keyCode=9; return event.keyCode }">
    <form id="fmHSE_Drill_Record_Hdr_Details" runat="server">

        <div style="left: 0px; width: 100%; position: absolute; top: 0px; height: 88%">
            <table style="width: 100%" class="table_header">
                <tr>
                  
                    <td class="td_button">
                        <asp:Button ID="btnSearch" runat="server" Text="Search" Width="100%" OnClientClick="Show_Main_Data();return false;"
                            CssClass="td_button" />
                    </td>

                    <td class="td_button">
                        <asp:Button ID="btnClear" runat="server" Text="Clear" Width="100%" CssClass="td_button"
                            OnClientClick="return SetPostbackFlag('CLEAR');" OnClick="btnClear_Click" />
                    </td>
                     <td class="td_button">
                        <asp:Button ID="btnPrint" runat="server" Text="Print" Width="100%" CssClass="td_button"
                            OnClientClick="return SetPostbackFlag('PRINT');" OnClick="btnPrint_Click" />
                    </td>
                    <td class="td_button"></td>
                    <td class="td_header" style="width: 40%">HSE Drill Details</td>
                </tr>
            </table>
            <br />


            <table class="table">
                <tr>
                    <td style="width: 19%"></td>
                    <td style="width: 12%"></td>
                    <td style="width: 20%"></td>
                    <td style="width: 19%"></td>

                    <td></td>

                </tr>

                <tr>
                    <td class="td_caption">
                        <span class="star">*</span> Rig
                    </td>
                    <td class="td">
                        <asp:TextBox ID="tbRig_Name" runat="server" CssClass="textbox_readonly" MaxLength="1"
                            onKeyDown="return RejectInput()" Width="100px"></asp:TextBox>&nbsp;</td>

                    <td class="td_caption">
                        <span class="star">*</span> Report No.
                    </td>
                    <td class="td" style="vertical-align: top">
                        <asp:TextBox ID="tbDrill_Record_No" runat="server" CssClass="textbox_readonly" OnKeyDown="return RejectInput();" Width="180px"
                            MaxLength="1"></asp:TextBox>
                    </td>
                    <td class="td_caption" style="vertical-align: top">
                        <span class="star">*</span> Drill Date/Time
                    </td>
                    <td class="td" style="vertical-align: top" colspan="3">

                        <asp:TextBox ID="tbDrill_Dt"
                            Width="70px" runat="server" CssClass="textbox_readonly" MaxLength="1"
                            onKeyDown="return RejectInput()"></asp:TextBox>
                        &nbsp;<asp:TextBox ID="tbDrill_Dt_Time" Width="40px"
                            runat="server" CssClass="textbox_readonly" MaxLength="1"
                            onKeyDown="return RejectInput()"></asp:TextBox>
                    </td>

                </tr>

                <tr>

                    <td class="td_caption">
                        <span class="star">*</span> Type of Drill/Training - 1
                    </td>
                    <td class="td">
                        <asp:TextBox ID="tbHSE_Drill_Id_1_Name" runat="server" CssClass="textbox_readonly" OnKeyDown="return RejectInput();"
                            Width="180px" MaxLength="1"></asp:TextBox>&nbsp;</td>


                    <td class="td_caption">Type of Drill /&nbsp;Training - 2
                    </td>
                    <td class="td">
                        <asp:TextBox ID="tbHSE_Drill_Type_2" runat="server" CssClass="textbox_readonly" OnKeyDown="return RejectInput();"
                            Width="180px" MaxLength="1"></asp:TextBox>&nbsp;</td>


                </tr>
            </table>

            <table style="width: 100%" class="table_header">
                <tr>
                    <td style="width:22%"></td>
                    <td style="width:22%"></td>
                    <td style="width:22%"></td>
                    <td style="width:22%"></td>
                    <td style="width:22%"></td>


                    <td class="auto-style2"></td>
                </tr>
                <% if (tbDrill_Record_Hdr_Id_Hidden.Value != "")
                   { %>
                <tr>

                    <td class="td_button">
                        <asp:LinkButton ID="btnEvents" runat="server" Text="Events" Width="100%"
                            CssClass="td_button" OnClick="btnEvents_Click"></asp:LinkButton>
                    </td>
                    <td class="td_button">
                        <asp:LinkButton ID="btnObservations" runat="server" Text="Observations" Width="100%"
                            CssClass="td_button" OnClick="btnObservations_Click"></asp:LinkButton>
                    </td>
                    <td class="td_button">
                        <asp:LinkButton ID="btnImprovements" runat="server" Text="Improvements" Width="100%"
                            CssClass="td_button" OnClick="btnImprovements_Click"></asp:LinkButton>
                    </td>
                    <td class="td_button">
                        <asp:LinkButton ID="btnCorrective_Action" runat="server" Text="Corrective Action" Width="100%"
                            CssClass="td_button" OnClick="btnCorrective_Action_Click"></asp:LinkButton>
                    </td>
                    <td class="td_button">
                        <asp:LinkButton ID="btnImage" runat="server" Text="Image" Width="100%"
                            CssClass="td_button" OnClick="btnImage_Click"></asp:LinkButton>
                    </td>
                </tr>
                <tr>
                    <td class="td_line" colspan="9"></td>
                </tr>
                <%} %>
            </table>
            <% if (tbDrill_Record_Hdr_Id_Hidden.Value != "")
               { %>
            <iframe id="frame1" name="frame1" scrolling="auto" runat="server" style=" height: 480px; width: 1500px;"></iframe>
            <%} %>
            <br />
            <input id="tbDrill_Record_Hdr_Id_Hidden" runat="server" name="tbDrill_Record_Hdr_Id_Hidden"
                style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px; height: 24px"
                type="hidden" />
              <input id="tbRig_Id_Hidden" runat="server" name="tbRig_Id_Hidden"
                style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px; height: 24px"
                type="hidden" />
            <input id="tbPostbackFlag_Hidden" runat="server" name="tbPostbackFlag_Hidden"
                style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px; height: 24px"
                type="hidden" />
        </div>
    </form>
</body>
</html>
