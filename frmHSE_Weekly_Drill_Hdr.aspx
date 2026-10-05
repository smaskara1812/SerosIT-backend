<%@ Page Language="C#" AutoEventWireup="true" CodeFile="frmHSE_Weekly_Drill_Hdr.aspx.cs"
    Inherits="Drills_frmHSE_Weekly_Drill_Hdr" %>

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Head1" runat="server">
    <title>HSE Weekly Drill</title>
    <link href="../../StyleSheet.css" type="text/css" rel="stylesheet" />
    <script type="text/javascript" language="javascript" src="../../Javascript/generic.js"> </script> 
    <script type="text/javascript" language="javascript" src="../../Javascript/Open_Search.js"> </script>
    <script type="text/javascript" language="javascript" src="../../Javascript/Open_ErrorWin.js"> </script>   
    <script type="text/javascript" language="javascript" src="../../JavaScript/jquery.min.js"></script>
    <script type="text/javascript" language="javascript" src="../../JavaScript/bootstrap.min.js"></script>
    <script type="text/javascript" language="javascript" src="../../JavaScript/CommonModal.js"></script>
    
    <link href="../../BootstrapStyleSheet.min.css" type="text/css" rel="stylesheet" />  

    <script type="text/javascript">
        window.onload = function () {   }

        function validate(strFlag) {
            SetPostbackFlag(strFlag);
            var strServerDt = '<%= Session["ServerDt"].ToString() %>';
            var msg = "";


            if (strFlag == 'DELETE') {
                if (document.getElementById('<%=tbHSE_Weekly_Drill_Hdr_Id_Hidden.ClientID%>').value == "") {
                    msg += "- Please Select record to Delete.<br><br>";
                }
                else {
                    var strErrMsg = "";
                    strErrMsg = "Are you sure you want to Delete this Record?";
                    var chk_Delete_Status = confirm(strErrMsg);
                    if (chk_Delete_Status == true) {
                        return true;
                    }
                    else {
                        return false;
                    }
                }
            }


            if (strFlag == "ADD") {
                if (document.getElementById('<%=tbHSE_Weekly_Drill_Hdr_Id_Hidden.ClientID%>').value != "") {
                    ShowMessage(400, 75, 'You are currently in Update mode. A new record cannot be added in this mode.');
                    return false;
                } 
            }
            else {
                if (document.getElementById('<%=tbHSE_Weekly_Drill_Hdr_Id_Hidden.ClientID%>').value == "") {
                    ShowMessage(400, 75, 'Select record to update.');
                    return false;
                }

            }
            document.getElementById('<%=tbRig_Name.ClientID%>').value = alltrim(document.getElementById('<%=tbRig_Name.ClientID%>').value);

            if (document.getElementById('<%=tbRig_Id_Hidden.ClientID%>').value == "") {
                msg += "- Rig must be selected.<br><br>";
                document.getElementById('<%=tbRig_Name.ClientID%>').focus();
            }
            if (document.getElementById('<%=tbDrill_Year.ClientID%>').value == "") {
                msg += "- Drill Year must be entered.<br><br>";
                document.getElementById('<%=tbDrill_Year.ClientID%>').focus();
            }

            if (document.getElementById('<%=tbDrill_Week.ClientID%>').value == "") {
                msg += "- Drill Week must be entered.<br><br>";
                document.getElementById('<%=tbDrill_Week.ClientID%>').focus();
            }

            else {

                if (parseInt(document.getElementById('<%=tbDrill_Week.ClientID%>').value) <= 0 &&
                    parseInt(document.getElementById('<%=tbDrill_Week.ClientID%>').value) > 52) {
                    msg += "- Drill_Week Between 1 and 52.<br><br>";
                    document.getElementById('<%=tbDrill_Week.ClientID%>').focus();
                }
            }


            if (msg == "") {

                return true;

            }
            else {
                ShowErrorWin1(msg);
                return false;
            }
        }

        function Validate(lnkUpdate, Type) {
            SetPostbackFlag(Type);
            var msg = "";

            var grdRow = lnkUpdate.parentNode.parentNode;
            var grdControl = grdRow.getElementsByTagName("input");

            var txtNewHSE_Drill_Name = grdRow.getElementsByTagName("input")[0];
            var txtNewDrill_Conducted_Dt = grdRow.getElementsByTagName("input")[2];
            var txtNewDrill_Last_Conducted_Dt = grdRow.getElementsByTagName("input")[3];
            var txtNewRemarks = grdRow.getElementsByTagName("input")[4];


            if (txtNewHSE_Drill_Name.value == "") {
                msg += "- Drill must be selected.<br><br>";
                txtNewHSE_Drill_Name.focus();
            }
            if (txtNewDrill_Conducted_Dt.value == "") {
                msg += "-  Drill Conducted date must be entered.<br><br>";
                txtNewDrill_Conducted_Dt.focus();
            }
            if (txtNewDrill_Last_Conducted_Dt.value == "") {
                msg += "-  Last Drill Conducted Date must be entered.<br><br>";
                txtNewDrill_Last_Conducted_Dt.focus();
            }

            //if (txtNewRemarks.value == "") {
            //    msg += "-  Remarks must be entered.<br><br>";
            //    txtNewRemarks.focus();
            //}

            if (txtNewDrill_Last_Conducted_Dt.value != "") {
                if (compareDates(txtNewDrill_Conducted_Dt.value, 'dd/MM/yyyy', txtNewDrill_Last_Conducted_Dt.value, 'dd/MM/yyyy') == 1) {
                }
                else {
                    msg += "- Drill Last Conducted date must be less than Drill Conducted date<br><br>";
                    txtNewDrill_Conducted_Dt.focus();
                }
            }

            if (txtNewDrill_Conducted_Dt.value != "") {

                if (!compareDates(document.getElementById('<%=tbStartOfWeek_Date_Hidden.ClientID%>').value, 'dd/MM/yyyy', txtNewDrill_Conducted_Dt.value, 'dd/MM/yyyy') == 0) {
                    msg += "-  Drill Completed Date must be greater than or equal to Week Start Date " + document.getElementById('<%=tbStartOfWeek_Date_Hidden.ClientID%>').value + "<br><br>";
                    txtNewDrill_Conducted_Dt.focus();
                }
                /////           Drill date                  Week start date
                if (compareDates(txtNewDrill_Conducted_Dt.value, 'dd/MM/yyyy', document.getElementById('<%=tbEndOfWeek_Date_Hidden.ClientID%>').value, 'dd/MM/yyyy') != 0) {
                    msg += "- Drill Completed Date must be less than or equal to Week End Date " + document.getElementById('<%=tbEndOfWeek_Date_Hidden.ClientID%>').value + "\n";
                    txtNewDrill_Conducted_Dt.focus();
                }
            }

            if (msg == "") {

                return true;

            }
            else {
                ShowErrorWin1(msg);
                return false;
            }

        }

        function ValidateUpdate(lnkUpdate, Type) {

            var strServerDt = '<%= Session["ServerDt"].ToString() %>';
            SetPostbackFlag(Type);
            var msg = "";

            var grdRow = lnkUpdate.parentNode.parentNode;
            var grdControl = grdRow.getElementsByTagName("input");

            var txtDrill_Conducted_Dt = grdRow.getElementsByTagName("input")[0];
            var txtRemarks = grdRow.getElementsByTagName("input")[1];
           
            if (txtDrill_Conducted_Dt.value == "") {
                msg += "- Drill Conducted Date must be entered.<br><br>";
                txtDrill_Conducted_Dt.focus();
            }
            //if (txtRemarks.value == "") {
            //    msg += "- Remarks must be entered.<br><br>";
            //    txtRemarks.focus();
            //}
             
            if (msg == "") { 
                return true; 
            }
            else {
                ShowErrorWin1(msg);
                return false;
            }
        }

        function Show_Main_Data() {
            SetPostbackFlag("SEARCH")
            var strSearchString = "%";
            Open_Search_Window('HSE_WEEKLY_DRILL_HDR', document.forms[0].name, 'tbHSE_Weekly_Drill_Hdr_Id_Hidden', 'tbRig_Name', '', strSearchString, 'Y', 'N', 'N');
            return;
        }
        function ShowRig() {
            SetPostbackFlag("RIG");
            var isPostback = "";
            if (document.getElementById('<%=tbDrill_Year.ClientID%>').value == "") {
                isPostback = "N";
            }
            else {
                isPostback = "Y";
            }


            Open_Search_Window('RIG', document.forms[0].name, 'tbRig_Id_Hidden', 'tbRig_Name', '', '', isPostback, 'Y', 'N');
            return;

        }
        function Check_Rig(obj) {
            document.getElementById('<%=tbDrill_Week.ClientID%>').value = "";

            if (document.getElementById('<%=tbRig_Id_Hidden.ClientID%>').value != "") {
                if (obj.value.length == 2) {

                    CheckYearOnBlur(obj);
                }

                if (obj.value.length == 4) {
                    SetPostbackFlag("YEAR");
                    __doPostBack();
                }
            }

        }
        function SetNextCnt() {
            if (document.getElementById('<%=tbPostbackFlag_Hidden.ClientID%>').value == "RIG") {
                document.getElementById('<%=tbDrill_Year.ClientID%>').focus();
            }
        }
        function CheckMaxLen(obj, length) {
            checkTextAreaMaxLength(obj, event, length);
        }

        function SetPostbackFlag(strFlag) {
            document.getElementById('<%=tbPostbackFlag_Hidden.ClientID%>').value = strFlag;
            return true;
        }

        function Get_Search_Selected_Row(arrSeleted_Row) {

        }



        function ChkPrintStatus(id) {

            var rows = document.getElementById('<%=grdContact.ClientID %>').getElementsByTagName('TR');
            for (var i = 0; i < rows.length; i++) {
                rows[i].className = 'GridView_RowStyle'; //if its your default color
            }
            document.getElementById(id.uniqueID).parentNode.parentNode.className = 'GridView_SelectedRowStyle';


            var chkdeletestatus = confirm("Are you sure you want to Delete this Record?");
            if (chkdeletestatus == true) {
                return true;
            }
            else {
                document.getElementById(id.uniqueID).parentNode.parentNode.className = 'GridView_RowStyle';
                return false;
            }
        }

        function Show_HSE_Drills(tbHSE_Drill_Id_Hidden, tbHSE_Drill_Name) {
            SetPostbackFlag("MST_HSE_DRILL");
            var strFilterString = " HSE_Drill_Id NOT IN (SELECT  HSE_Drill_Id FROM eos.HSE_Weekly_Drill_Dtl WHERE  HSE_Weekly_Drill_Hdr_Id =" + document.getElementById('<%=tbHSE_Weekly_Drill_Hdr_Id_Hidden.ClientID%>').value + ")";

            if (parseInt(document.getElementById('<%=tbRig_Id_Hidden.ClientID%>').value) == 1)
            {
                strFilterString += "and  ISNULL(Rig_Type_Id,0) <>2";//Get DRILL which is for Offshore only
                //2	Onshore Rig
            }           
            else
            {
                strFilterString += "and  ISNULL(Rig_Type_Id,0) <>1";//Get DRILL which is for Onshore only
                //1	Offshore Rig
            }
                
            Open_Search_Window('MST_HSE_DRILL', document.forms[0].name, tbHSE_Drill_Id_Hidden.id, tbHSE_Drill_Name.id, strFilterString, '%', 'N', 'Y', 'N');
            return;
        }

        function Get_Last_Drill_Conducted_Date(tbHSE_Drill_Id_Hidden, txtNewDrill_Conducted_Dt) {

            if (document.getElementById(txtNewDrill_Conducted_Dt.id).value != "") {

                SetPostbackFlag("GET_LAST_DRILL_CONDUCTED_DATE");

                var IsValid = CheckDateOnBlur(document.getElementById(txtNewDrill_Conducted_Dt.id));//Convert it in to 10 digit
                {
                    if (document.getElementById(tbHSE_Drill_Id_Hidden.id).value == "") {
                        document.getElementById(txtNewDrill_Conducted_Dt.id).value="";
                        alert('Drill must be selected first');
                        
                        return;
                    }
                }
                __doPostBack();
            }
        }
    </script> 

</head>
<body class="body" onkeydown="if (event.keyCode==13) {event.keyCode=9; return event.keyCode }">
    <form id="frmHSE_Weekly_Drill_Hdr" runat="server">
        <div style="left: 0px; width: 100%; position: absolute; top: 0px; height: 88%">
            <table style="width: 100%" class="table_header">
                <tr>
              
                    <td class="td_button">
                        <asp:Button ID="btnSearch" runat="server" Text="Search" Width="100%" OnClientClick="Show_Main_Data();return false;"
                            CssClass="td_button" />
                    </td>
                    <td class="td_button">
                        <asp:Button ID="btnAdd" runat="server" Text="Add" Width="100%" OnClick="btnAdd_Click"
                            CssClass="td_button" OnClientClick="return validate('ADD')" />
                    </td>
                    <%-- <td class="td_button">
                        <asp:Button ID="btnUpdate" runat="server" Text="Update" Width="100%" CssClass="td_button"
                            OnClientClick="return validate('UPDATE')" OnClick="btnUpdate_Click" />
                    </td>--%>
                    <td class="td_button">
                        <asp:Button ID="btnDelete" runat="server" Text="Delete" Width="100%" CssClass="td_button"
                            OnClientClick="return validate('DELETE')" OnClick="btnDelete_Click" />
                    </td>
                    <td class="td_button">
                        <asp:Button ID="btnClear" runat="server" Text="Clear" Width="100%" CssClass="td_button"
                            OnClick="btnClear_Click" OnClientClick="return SetPostbackFlag('CLEAR');" />
                    </td>

                    <td class="td_button">&nbsp;
                    </td>
                    <td class="td_header" style="width: 40%">HSE Weekly Drill</td>
                </tr>
            </table>
            <br />
            <table class="table">
                <tr>
                    <td style="width: 15%"></td>
                    <td style="width: 15%"></td>
                    <td style="width: 8%"></td>
                    <td style="width: 8%"></td>
                    <td style="width: 8%"></td>
                    <td style="width: 15%"></td>
                    <td style="width: 8%"></td>

                    <td></td>
                </tr>

                <tr>


                    <td class="td_caption">
                        <span class="star">*</span>&nbsp;Rig
                    </td>
                    <td class="td">
                        <asp:TextBox ID="tbRig_Name" runat="server" CssClass="textbox_readonly" OnKeyDown="return RejectInput();"
                            ReadOnly="False" Width="110px" onblur="SetNextCnt();" MaxLength="1"></asp:TextBox>&nbsp;<asp:ImageButton
                                ID="ibtnRig_Name" runat="server" OnClientClick="ShowRig();return false;"
                                ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Rig"
                                CssClass="image_search" />
                    </td>
                    <td class="td_caption">Year </td>
                    <td class="td">
                        <asp:TextBox ID="tbDrill_Year"
                            runat="server" CssClass="textbox" MaxLength="4" onKeyUp="Validate_Numeric(this);"
                            Width="30px" OnBlur="return CheckYearOnBlur(this);" onchange="Check_Rig(this);"></asp:TextBox>


                    </td>
                    <td class="td_caption">Week </td>
                    <td class="td">
                        <asp:TextBox ID="tbDrill_Week" runat="server"
                            AutoPostBack="false" CssClass="textbox_readonly" MaxLength="2"
                            Width="14px" OnKeyDown="return RejectInput();"
                            ToolTip="Numeric Values Only"></asp:TextBox>


                    </td>
                </tr>

            </table>
            <div id="divHelpData1" class="div_gridview1" style="float: left; width: 100%; height: 360px">

                <table class="table">
                    <tr>
                        <td>
                            <asp:GridView ID="grdContact" CssClass="GridView" Width="90%" runat="server"
                                AutoGenerateColumns="False" DataKeyNames="HSE_Weekly_Drill_Dtl_Id"
                                ShowFooter="True" OnRowCommand="grdContact_RowCommand"
                                OnRowCancelingEdit="grdContact_RowCancelingEdit"
                                OnRowEditing="grdContact_RowEditing"
                                OnRowUpdating="grdContact_RowUpdating"
                                OnSelectedIndexChanged="grdContact_SelectedIndexChanged"
                                OnDataBound="grdContact_DataBound" OnRowDataBound="grdContact_RowDataBound">
                                <Columns>
                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="ID" Visible="false">
                                        <EditItemTemplate>
                                            <asp:Label ID="lblId" CssClass="textbox" runat="server" Text='<%# Bind("HSE_Weekly_Drill_Dtl_Id") %>'></asp:Label>
                                        </EditItemTemplate>
                                        <ItemTemplate>
                                            <asp:Label ID="lblId0" runat="server" Text='<%# Bind("HSE_Weekly_Drill_Dtl_Id") %>'></asp:Label>
                                        </ItemTemplate>
                                        <ItemStyle />
                                        <HeaderStyle HorizontalAlign="Left"></HeaderStyle>
                                    </asp:TemplateField>




                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="HSE Drill Name*">
                                        <EditItemTemplate>
                                            <asp:Label ID="txtHSE_Drill_Name" runat="server" Text='<%# Bind("HSE_Drill_Name") %>'></asp:Label>
                                        </EditItemTemplate>
                                        <FooterTemplate>
                                            <asp:TextBox ID="txtNewHSE_Drill_Name" CssClass="textbox_readonly" onKeyDown="return RejectInput()" Width="290px" runat="server"></asp:TextBox>
                                            <asp:ImageButton ID="ibtnNewHSE_Drill" runat="server" ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" ToolTip="Find HSE Drill Name"
                                                CssClass="image_search" />
                                        </FooterTemplate>
                                        <ItemTemplate>
                                            <asp:Label ID="lblHSE_Drill_Name" runat="server" Text='<%# Bind("HSE_Drill_Name") %>'></asp:Label>
                                        </ItemTemplate>
                                        <HeaderStyle HorizontalAlign="Left" Width="350px"></HeaderStyle>
                                        <ItemStyle HorizontalAlign="Center" CssClass="textbox" Width="350px" />
                                        <FooterStyle HorizontalAlign="Center" CssClass="textbox" Width="350px" />

                                    </asp:TemplateField>

                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="Drill Conducted Date *">
                                        <EditItemTemplate>
                                            <asp:TextBox ID="txtDrill_Conducted_Dt" CssClass="textbox" runat="server" Text='<%# Bind("Drill_Conducted_Dt") %>' MaxLength="10" Width="70px"
                                                OnKeyUp="return DateMask(this);" OnBlur="return CheckDateOnBlur(this);"></asp:TextBox>
                                        </EditItemTemplate>
                                        <FooterTemplate>
                                            <asp:TextBox ID="txtNewDrill_Conducted_Dt" CssClass="textbox" runat="server" MaxLength="10" Width="70px"
                                    OnKeyUp="return DateMask(this);" OnBlur="return CheckDateOnBlur(this);" onchange="Get_Last_Drill_Conducted_Date();"></asp:TextBox>
                                        </FooterTemplate>
                                        <ItemTemplate>
                                            <asp:Label ID="lblDrill_Conducted_Dt" runat="server" Text='<%# Bind("Drill_Conducted_Dt") %>'></asp:Label>
                                        </ItemTemplate>
                                        <HeaderStyle HorizontalAlign="Left" Width="110px"></HeaderStyle>
                                        <ItemStyle HorizontalAlign="Center" CssClass="textbox" Width="110px" />
                                        <FooterStyle HorizontalAlign="Center" CssClass="textbox" Width="110px" />

                                    </asp:TemplateField>
                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="Last Drill Conducted Date *">
                                        <EditItemTemplate>


                                            <asp:Label ID="txtDrill_Last_Conducted_Dt" runat="server" Text='<%# Bind("Drill_Last_Conducted_Dt") %>'></asp:Label>
                                        </EditItemTemplate>
                                        <FooterTemplate>
                                            <asp:TextBox ID="txtNewDrill_Last_Conducted_Dt" CssClass="textbox" runat="server" MaxLength="10" Width="70px"
                                                OnKeyUp="return DateMask(this);" OnBlur="return CheckDateOnBlur(this);"></asp:TextBox>
                                        </FooterTemplate>
                                        <ItemTemplate>
                                            <asp:Label ID="lblDrill_Last_Conducted_Dt" runat="server" Text='<%# Bind("Drill_Last_Conducted_Dt") %>'></asp:Label>
                                        </ItemTemplate>
                                        <HeaderStyle HorizontalAlign="Left" Width="110px"></HeaderStyle>
                                        <ItemStyle HorizontalAlign="Center" CssClass="textbox" Width="110px" />
                                        <FooterStyle HorizontalAlign="Center" CssClass="textbox" Width="110px" />

                                    </asp:TemplateField>
                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="Remarks">
                                        <EditItemTemplate>                                          
                                            <asp:TextBox ID="txtRemarks" runat="server" CssClass="textbox" MaxLength="150" Text='<%# Bind("Remarks") %>' 
                                                Width="290px"></asp:TextBox>
                                        </EditItemTemplate>
                                        <FooterTemplate>

                                            <asp:TextBox ID="txtNewRemarks" runat="server" CssClass="textbox" MaxLength="150"
                                                Width="290px"></asp:TextBox>

                                        </FooterTemplate>
                                        <ItemTemplate>
                                            <asp:Label ID="lblRemarks" runat="server" Text='<%# Bind("Remarks") %>'></asp:Label>
                                        </ItemTemplate>
                                        <HeaderStyle HorizontalAlign="Left" Width="150px"></HeaderStyle>
                                        <ItemStyle HorizontalAlign="Center" CssClass="textbox" Width="150px" />
                                        <FooterStyle HorizontalAlign="Center" CssClass="textbox" Width="150px" />
                                    </asp:TemplateField>


                                    <asp:TemplateField HeaderText="" HeaderStyle-CssClass="hiddencol" ItemStyle-CssClass="hiddencol">
                                        <FooterTemplate>
                                            <input id="tbHSE_Drill_Id_Hidden" runat="server" name="tbHSE_Drill_Id_Hidden" style="z-index: 104; left: 43px; width: 1px; position: absolute; top: 258px; height: 24px"
                                                type="hidden"
                                                value='<%# Bind("HSE_Drill_Id") %>' />
                                        </FooterTemplate>
                                        <HeaderStyle CssClass="hiddencol"></HeaderStyle>
                                        <ItemStyle CssClass="hiddencol"></ItemStyle>
                                        <FooterStyle CssClass="hiddencol" />

                                    </asp:TemplateField>


                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="Edit" ShowHeader="False">
                                        <EditItemTemplate>
                                            <asp:LinkButton ID="lbkUpdate" runat="server" CausesValidation="True" CommandName="Update" Text="Update" OnClientClick="return ValidateUpdate(this,'Update')"></asp:LinkButton>
                                            <asp:LinkButton ID="lnkCancel" runat="server" CausesValidation="False" CommandName="Cancel" Text="Cancel"></asp:LinkButton>
                                        </EditItemTemplate>
                                        <FooterTemplate>
                                            <asp:LinkButton ID="lnkAdd" runat="server" CausesValidation="False" CommandName="Insert" Text="Insert" OnClientClick="return Validate(this,'Insert')"></asp:LinkButton>
                                        </FooterTemplate>
                                        <ItemTemplate>
                                            <asp:LinkButton ID="lnkEdit" runat="server" CausesValidation="False" CommandName="Edit" Text="Edit"></asp:LinkButton>
                                        </ItemTemplate>
                                    </asp:TemplateField>
                                    <asp:TemplateField HeaderText="Delete">
                                        <EditItemTemplate>
                                            <asp:LinkButton ID="ilnkDelete" runat="server"></asp:LinkButton>
                                        </EditItemTemplate>
                                        <FooterTemplate>
                                            <asp:LinkButton ID="lnkDelete" runat="server"></asp:LinkButton>
                                        </FooterTemplate>
                                        <ItemTemplate>
                                            <asp:LinkButton ID="lnkDelete0" CommandName="cmdDelete" Text="Delete" runat="server"
                                                CommandArgument='<%# Eval("HSE_Weekly_Drill_Dtl_Id") %>' OnClientClick="javascript:return ChkPrintStatus(this);"></asp:LinkButton>
                                        </ItemTemplate>
                                    </asp:TemplateField>
                                </Columns>
                            </asp:GridView>
                        </td>
                    </tr>
                </table>
            </div>
            <table class="table">
            </table>
            <input id="tbHSE_Weekly_Drill_Hdr_Id_Hidden" runat="server" name="tbHSE_Weekly_Drill_Hdr_Id_Hidden"
                style="z-index: 104; left: 105px; width: 24px; position: absolute; top: 329px; height: 24px"
                type="hidden" value="" />
            <input id="tbRig_Id_Hidden" runat="server" name="tbRig_Id_Hidden" style="z-index: 104; left: 402px; width: 24px; position: absolute; top: 262px; height: 24px"
                type="hidden" />
            <input id="tbStartOfWeek_Date_Hidden" runat="server" name="tbStartOfWeek_Date_Hidden" style="z-index: 104; left: 165px; width: 24px; position: absolute; top: 291px; height: 24px"
                type="hidden" />
            <input id="tbEndOfWeek_Date_Hidden" runat="server" name="tbEndOfWeek_Date_Hidden" style="z-index: 104; left: 165px; width: 24px; position: absolute; top: 291px; height: 24px"
                type="hidden" />
            <input id="tbPostbackFlag_Hidden" runat="server" name="tbPostbackFlag_Hidden" style="z-index: 104; left: 165px; width: 24px; position: absolute; top: 291px; height: 24px"
                type="hidden" />

        </div>
        <asp:LinkButton ID="LinkButton1" runat="server" Style="display: none">LinkButton</asp:LinkButton>
    </form>
</body>
</html>
